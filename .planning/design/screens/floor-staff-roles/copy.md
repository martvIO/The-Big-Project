# Copy deck — F57 Floor staff cards + break status (`apps/manage`, `FloorPanel` and the section «הצוות בקומה»)

**Date**: 2026-07-31 · **Status**: **DRAFTED under the approved register, self-approved with the design gate** — Interview **Q2** named only F34's board and F42's capacity matrix as novel patterns for this run (`LOOP-STATE.md:1054`), and a staff-cards panel assembled from F34's shipped shell is neither. **The Hebrew remains the user's to edit post-merge** — the F15 P-1/P-5 and F34 precedent: a one-line `he.ts` / `ar.ts` edit after merge, never a rebuild. Console copy, not a customer-facing SMS, so there is no counsel gate · **Owner of the Hebrew: the user** · **Consumes**: `.planning/specs/floor-staff-roles.md` (**D1–D14**) and `design.md` in this directory · **Lands in**: `Frontend/apps/manage/src/i18n/he.ts` (`nav.floor`, a new `floor.*` namespace, three additions to F51's `staff.*`) **and `…/i18n/ar.ts`**, same keys, Hebrew standing in untranslated.

**F57 adds no SMS template, sends no message and touches no `comms_templates.py` body.** There is no §SMS section in this deck and there cannot be one: a break toggle writes one timestamp and one audit row (spec D7, D8). Nothing on this screen has any occasion to mention anyone being told anything.

**Three of these strings correct a proposal in the spec rather than transcribing it**, and each is recorded in `design.md` §9 rather than folded in silently: **F-2** (`floor.pauseAria`, a WCAG 2.5.3 label-in-name failure in the wording proposed at spec **D12**`:457`), **F-3** (`floor.breakSince`, which repeated the word the `Badge` above it already carries — proposed at **D13**), and **F-10** (the reuse of the shipped `staff.loadFailed` in place of D13's proposed `floor.outage`, with the namespace objection answered). A reviewer diffing this deck against D12/D13's proposed copy will find the reasons here.

**A fourth string is changed after review**, and it is the one below with no spec proposal behind it: `floor.idleStopped` now **names its region** — `design.md` §9 **F-4**. `board.idleStopped` (`he.ts:488`) is byte-identical to the string this deck first proposed, both go into a `role="status"` region, and both idle windows are reset by the same global interactions, so a screen-reader user heard one sentence twice with nothing saying which surface stopped.

## 0. The rules this deck is written under — hard constraints, not preferences

1. **Zero exclamation marks** (pre-decided #5). Mechanically checkable, and `__tests__/i18n.test.ts` already reads for it.
2. **Never claim, promise or hedge that a message was sent, in any tense.** Trivially satisfied — the feature sends nothing — and stated anyway, because "we let the team know she is on a break" is the exact sentence a well-meaning editor would add to a break cue.
3. **The panel states, it does not reassure.** Every string is a fact, and the ones about time have a time on them. No «הכל תקין», no «מעולה», no encouragement. A staffer reads this screen fifty times a shift and warmth at that frequency is noise.
4. **Freshness is claimed weakly and honestly.** «עודכן 14:07» says *this was true at 14:07*. Nothing anywhere says «בזמן אמת» or «חי» — the panel polls, and a claim it cannot keep even for one interval is worse than the truth.
5. **No string names or implies a retry interval** (F34's rule 9, inherited through `usePoll`'s backoff). Consecutive failures stretch the interval 5s → ~60s, so «הרשימה תתעדכן מיד» is true at tick 1 and false by tick 5. The stale copy states **what is unknown**, never **when it will be known**, and the one row-level error names the **event** («בעדכון הבא»), never a duration.
6. **The 403 body is generic by design and may not be made specific** (F34's rule 10). `NotAuthorizedError` ships one body for every unadmitted role (`auth/dependencies.py:17-21`) so a probe cannot learn which roles exist. Naming a role, or saying what changed, would be an invention the server never made — and on the demotion path it would be the product telling a staffer she was demoted, which is her manager's sentence to say, not a screen's.
7. **Status and role are carried by WORDS.** The `Badge`'s colour is reinforcement and never the signal (`design.md` §2.3), which is F51's shipped rule — *"The WORD carries the role; the colour never does"* (`StaffSection.tsx:303-305`). **The brief's 🟢/🟡/🔵 do not ship as glyphs**: an emoji is announced by a screen reader with a name this product did not choose and cannot translate, and the console ships no icon vocabulary at all.
8. **Reuse F51's keys wherever this panel says the same thing about the same thing** — the two shipped role words, the self marker and the staff-list outage sentence are **reused, not re-declared**. A second spelling of «בעלת הבוטיק» in one console would be a defect.
9. **Every value is a real string.** No `…`-as-placeholder, no Lorem, nothing to be filled in later. The one `…` in this deck is inside `floor.loading`, where it is the content.
10. **The `ar` column is the approved Hebrew, standing in untranslated** (Interview Q3 / pre-decided #47 / the 2026-07-31 languages ruling), and it is **never an empty string**: i18next's `returnEmptyString` default renders `""` rather than falling back, so a premature switch would blank the page instead of showing Hebrew. `lng` stays `"he"`, `fallbackLng` stays `"he"`, no switcher ships.

**32 keys invented, 4 reused.** `nav.floor`, 28 under `floor.*`, and three role words added to F51's existing `staff.*` namespace. The four reused rows are marked **SHIPPED** and must never be counted into the 32 or re-declared.

---

## 1. Navigation and section chrome

| Key | What it must say | Approved Hebrew (`he`) | `ar` (untranslated) | Status |
|---|---|---|---|---|
| `nav.floor` | The **eleventh** console nav item (`App.tsx:18-27` carries ten `SectionKey` members and ten `NAV` rows; an earlier draft of this row said "eighth"), rendered **only** for reception / sales_assistant / seamstress (spec D11 — the owner and the shift manager reach the same panel under «לוח היום» and get no second row). For those three roles this is the **only** row they will ever see, so it names a destination: «הצוות בקומה», not «צוות» — that word is already taken one role up by F51's owner-only section, and not «קומה» alone, which names a place and not what is on it | הצוות בקומה | הצוות בקומה | DRAFTED |
| `floor.heading` | The panel `h2`. Indefinite, unlike the nav row, because for two of the five roles it sits directly beneath «לוח היום» as the second heading on one screen, where «הצוות בקומה» would read as a nav label that wandered into the page | צוות בקומה | צוות בקומה | DRAFTED |

## 2. The freshness row — the whole live-ness contract, and it is never announced

**Ten of this deck's strings are byte-identical to F34's `board.*` equivalents and are still declared separately**, which is a deliberate cost and is recorded as `design.md` **F-9**. The short version: the board's keys are namespaced to a screen three of the five roles cannot open, and renaming them into a shared `poll.*` namespace would edit `BoardSection`'s i18n — which spec D10 forbids in this PR, because `BoardSection.test.tsx` must pass **unedited**.

| Key | What it must say | Approved Hebrew (`he`) | `ar` | Status |
|---|---|---|---|---|
| `floor.updatedAt` | The freshness claim, at the row's inline-end. Changes **only when a fetch succeeds**, so it is a claim the panel can keep. Past tense on purpose | עודכן {{time}} | עודכן {{time}} | DRAFTED — `{{time}}` is `jerusalemTime()`, `HH:MM`, inside `<bdi dir="ltr">` |
| `floor.staleAt` | Replaces `floor.updatedAt` after a failed tick, in `--color-warning-text font-semibold` (F34's **P-6**, ruled and shipped). The cards are still on screen and still correct as of that time — which is exactly why this must be legible rather than muted: plausible-looking data beside a grey notice is what gets scanned past | אין עדכון מאז {{time}} | אין עדכון מאז {{time}} | DRAFTED |
| `floor.staleBody` | The line under it. Says what is unknown, not what is wrong — the panel cannot tell a dead wifi from a dead server and pretending otherwise would be a guess. No apology, no «אנא», and **no interval** (§0 rule 5) | ייתכן שהמידע אינו עדכני. | ייתכן שהמידע אינו עדכני. | DRAFTED |
| `floor.refresh` | The retry button, present in the stale state and in the first-load failure. **Never** rendered in the paused or idle state — the resume control is the affordance there, and «רענון» beside «חידוש» is two Hebrew words a hurried reader will not tell apart | רענון | רענון | DRAFTED |

### 2.1 The pause / resume control and the idle stop — WCAG 2.0 SC 2.2.2, and it is a legal item

**Eight keys.** Spec **D12**: the panel is a second auto-updating surface on the same screen, so it carries its own mechanism — Level A, inside an AA bar that pre-decided #38 makes **legal**, and **axe has no rule for 2.2.2**, so no automated check will ever tell us a string here is missing. For the three floor roles this is the *only* pause control on their *only* screen.

| Key | What it must say | Approved Hebrew (`he`) | `ar` | Status |
|---|---|---|---|---|
| `floor.pause` | The control's visible label while the panel is updating. Two syllables, and **identical to the board's** on purpose: one product vocabulary, and a staffer looking at two stopped regions must not have to learn that «השהיה» and «עצירה» are the same act. Not «עצור» (a stop, and this is reversible in one tap), not «הקפאה» (a freeze implies the data froze; the data is fine, the *fetching* stopped) | השהיה | השהיה | **APPROVED** (spec D12) |
| `floor.pauseAria` | Its accessible name. «השהיה» alone, on a screen carrying **two** pause controls, does not say which region it stops. ⚠ **Not spec D12's proposed «השהיית עדכון הצוות»** (`:457` — D12, not D13; D13's table carries `floor.breakSince`, not this key): the visible label is «השהיה», «השהיית» is a different word form, so that name would not contain its own visible label — WCAG 2.5.3 label-in-name, and a speech-input user saying «השהיה» would match nothing (`design.md` **F-2**) | השהיה — עדכון הצוות | השהיה — עדכון הצוות | **APPROVED** — `aria-label` only, never rendered |
| `floor.resume` | The same control once stopped — **one button whose name changes**, not two buttons, and not `aria-pressed`. Not «רענון»: that word is taken above for the one-shot retry, and the two acts differ (one fetch now vs. start the beat again) | חידוש | חידוש | **APPROVED** |
| `floor.resumeAria` | Same rule, same `—` shape | חידוש — עדכון הצוות | חידוש — עדכון הצוות | **APPROVED** — `aria-label` only |
| `floor.pausedAt` | Replaces `floor.updatedAt` at the inline-end whenever the loop is stopped, in the **identical** `--color-warning-text` escalation `floor.staleAt` gets, for the identical reason: a panel *she* paused is easier to forget than one that broke. Serves both the manual pause and the idle stop; the body line below says which | מושהה · עודכן {{time}} | מושהה · עודכן {{time}} | **APPROVED** — `{{time}}` inside `<bdi dir="ltr">` |
| `floor.paused` | The body line after a **manual** pause. States the consequence, does not apologise for it and does not thank her for it — she asked for this. Names the staff list rather than «הלוח», because for three of the five roles there is no board on the screen at all | העדכון מושהה. רשימת הצוות לא תתעדכן עד לחידוש. | העדכון מושהה. רשימת הצוות לא תתעדכן עד לחידוש. | **APPROVED** |
| `floor.idleStopped` | The body line after the **idle** stop. Names the cause, because the difference between "I paused this" and "this paused itself" is the whole difference between a control and a bug — **and names the REGION**, because it is not the only surface that stops. ⚠ **Revised after review** (`design.md` §9 **F-4**): the first draft was «העדכון הופסק אחרי…», byte-identical to the shipped `board.idleStopped` (`he.ts:488`). Both go into a `role="status"` region and both idle windows are reset by the same global interactions, so on the board screen the two fire within a frame and a screen-reader user hears **the same sentence twice**, back to back, with nothing saying which stopped. The idle stop is the one 2.2.2 event that fires without a tap, so it is the one case where both regions announce automatically. `floor.paused` already names «רשימת הצוות»; this now matches. One interpolation, so `isolateLtr` is reused unchanged | עדכון הצוות הופסק אחרי {{minutes}} דקות ללא פעילות. | עדכון הצוות הופסק אחרי {{minutes}} דקות ללא פעילות. | **APPROVED** — `{{minutes}}` inside `<bdi dir="ltr">`; the value is `IDLE_STOP_MS` = 10 minutes, F34's **P-8**, already shipped |
| `floor.resumed` | The announced cue on resume, in the existing `role="status"` region. Not symmetry: on resume the button's own accessible name flips, and a screen reader does **not** reliably re-announce the name of a control that is already focused — so without this string the one confirmation a sighted user gets for free is denied to the user 2.2.2 exists for | העדכון חודש. | העדכון חודש. | **APPROVED** |

**What is announced, and what is not.** Pausing, idle-stopping and resuming are all **user-initiated outcomes** — an idle stop is the consequence of her *not* acting, which she still caused — so all three go through the existing `role="status"` cue, exactly what spec D12 admits there. `floor.paused` and `floor.idleStopped` are announced **and** rendered as the body line; `floor.resumed` is announced only. No new region, no `role="alert"` — nothing here is an emergency.

**Declined: a frequency picker.** 2.2.2 is satisfied by *any one* of pause / stop / hide / control-frequency, and a picker is a settings surface, a persisted preference, a second constant and three more strings for a criterion one button closes.

## 3. The card — the status, the fact under it, and the one action

| Key | What it must say | Approved Hebrew (`he`) | `ar` | Status |
|---|---|---|---|---|
| `floor.statusAvailable` | The `Badge` word on a staffer who is not on a break. Feminine, like every persona word in this product. Not «זמינה» (which reads as an availability *setting* she configured), not «פנוי» | פנויה | פנויה | DRAFTED |
| `floor.statusBreak` | The `Badge` word on a staffer whose `break_started_at` is set. The status is `break` and **nothing else can be rendered** — `occupied` is F36's and is not on the wire (spec D9), so no string for it exists here and none may be invented in advance | בהפסקה | בהפסקה | DRAFTED |
| `floor.breakSince` | The fact line under the role, rendered **only** on a break. ⚠ **Not spec D13's proposed «בהפסקה מ־{{time}}»**: the `Badge` immediately above already reads «בהפסקה», and repeating it spends 295px of a 375px card saying one thing twice — which also makes two signals look like two facts (`design.md` **F-3**). It is `--color-ink`, not muted: on this panel it is the operative fact. **It is what makes a forgotten break legible** rather than silent, since nothing but a tap ever ends one | מאז {{time}} | מאז {{time}} | DRAFTED — `{{time}}` inside `<bdi dir="ltr">` |
| `floor.breakStart` | The control on an available staffer. Two syllables, because it lives under a thumb on a 375px phone. «להפסקה» — where she is going — rather than «התחלת הפסקה», which is a form label, not a button | להפסקה | להפסקה | DRAFTED |
| `floor.breakStartAria` | Its accessible name. Five buttons all named «להפסקה» is a screen-reader dead end, and the name **starts with the visible label** so WCAG 2.5.3 label-in-name holds | להפסקה — {{name}} | להפסקה — {{name}} | DRAFTED — `aria-label` only, never rendered |
| `floor.breakEnd` | The control on a staffer who is on a break. «חזרה» — she is coming back — not «סיום הפסקה» (an administrative act performed on a record) and not «פנויה», which is the status word and would make the button and the `Badge` say the same thing while meaning different ones | חזרה | חזרה | DRAFTED |
| `floor.breakEndAria` | Same rule | חזרה — {{name}} | חזרה — {{name}} | DRAFTED — `aria-label` only |

**No string for "you may not do this".** A staffer without permission on a colleague's card sees **no control at all** — no disabled button, no lock, no explanation (`design.md` §2.2). The absence is cosmetics; the control is the server's identity check (spec D6), which is why there is nothing here to word.

### 3.1 The role words — three new, two shipped, and one record binds all five

The role word is read from `ROLE_LABEL_KEY: Record<StaffRole, string>` in `lib/roles.ts` (spec D13), shared by `FloorPanel` and F51's `StaffSection`. The `Record` type makes a missing member a **compile error**; `__tests__/i18n.test.ts` resolving every value makes a missing key a **red test**. Both halves are needed: the type cannot see i18n and i18n cannot see the union.

| Key | What it must say | Approved Hebrew (`he`) | `ar` | Status |
|---|---|---|---|---|
| `staff.roleOwner` | — | בעלת הבוטיק | בעלת הבוטיק | **SHIPPED — reused, not invented** (`he.ts:207`) |
| `staff.roleShiftManager` | — | אחראית משמרת | אחראית משמרת | **SHIPPED — reused** (`he.ts:208`). ⚠ Until this feature, `StaffSection.tsx:99-100` resolved the role with a two-branch ternary that returns **this string for anything that is not `owner`** — so without the record a seamstress is labelled «אחראית משמרת» on the staff screen. That is the frontend form of "widening the enum widens nothing", and it is a defect this feature *creates* if the record is skipped |
| `staff.roleReception` | The `reception` word. «קבלה» — the desk and the function, the word a boutique already uses out loud. Not «פקידת קבלה» (an office title) | קבלה | קבלה | DRAFTED |
| `staff.roleSalesAssistant` | The `sales_assistant` word. The slug is `'sales_assistant'`, superseding pre-decided #24's `'sales'` by the 2026-07-31 roles ruling. «יועצת מכירות» — she advises a bride through a fitting; «מוכרת» is a shop counter and «נציגת מכירות» is a call centre | יועצת מכירות | יועצת מכירות | DRAFTED |
| `staff.roleSeamstress` | The `seamstress` word. «תופרת» — the trade word. Not «חייטת» (a tailor, who cuts) and not «מתקנת» (which names the repair, not the person) | תופרת | תופרת | DRAFTED |
| `staff.selfMarker` | The muted marker on her own card, exactly as on F51's staff row. There is no empty state for this list in practice — she is always in it | זו את | זו את | **SHIPPED — reused** (`he.ts:209`) |

## 4. The announced cues — user-initiated only, and they name the colleague

The `role="status"` region carries **nothing the poll produces** (spec D12). Every string below is the direct consequence of a tap, and `floor.loading` fires once on a first load nobody else can trigger.

**A cue is spoken once per tap, and staying on screen is not speaking again.** Neither cue is cleared on a timer — once tapped, it remains visible until the next tap replaces it. That is only safe because the region is **written only when its value changes** (F34's **F-7**, measured with a `MutationObserver`): re-asserting an unchanged string into `role="status"` still replaces the text node and still announces, so a five-second repaint that "kept the cue the same" would read «נרשמה הפסקה עבור נועה לוי.» aloud every five seconds until the end of the shift.

**They name the colleague.** «נרשמה הפסקה.» after tapping one of five cards cannot confirm *which* colleague, which makes the cue useless exactly when the panel is busy. This is a colleague's display name announced to a colleague, on a payload every staffer can already read — not a customer's name, which is why F15's rule about the bride's name in a persistent landmark does not reach it.

| Key | What it must say | Approved Hebrew (`he`) | `ar` | Status |
|---|---|---|---|---|
| `floor.loading` | Carried by the cue region on the **first** load only. The shipped console announces nothing while loading; this panel closes that for itself by reusing the region it already needs | טוען את רשימת הצוות… | טוען את רשימת הצוות… | DRAFTED |
| `floor.breakStartedCue` | After a successful start — **and after a no-op 200**, when another staffer got there first and the server kept the first timestamp (spec D7's middle row). Identical, deliberately: the outcome she wanted is the outcome that holds, and telling her she lost a race would be telling her she was wrong when she was right | נרשמה הפסקה עבור {{name}}. | נרשמה הפסקה עבור {{name}}. | DRAFTED — `{{name}}` rendered inside a bare `<bdi>` |
| `floor.breakEndedCue` | After a successful end, and after its no-op for the same reason | ההפסקה הסתיימה עבור {{name}}. | ההפסקה הסתיימה עבור {{name}}. | DRAFTED |

## 5. States

| Key | What it must say | Approved Hebrew (`he`) | `ar` | Status |
|---|---|---|---|---|
| `staff.loadFailed` | The **first** fetch failed and there is nothing on screen — the **outage** register: recoverable, unblaming, no technical words. ⚠ **Reused rather than D13's proposed new `floor.outage`** (§0 rule 8; recorded as `design.md` §9 **F-10**, which also corrects §4's F-fail cell and answers why reusing F51's **owner-only** `staff.*` namespace is right here where F-9 refused to reuse `board.*` — the short version: `staff.loadFailed` names its **subject**, which is this panel's payload; `board.*` names a **screen** three of the five roles cannot open): it is the same sentence about the same subject — the boutique's staff list failing to load — and two byte-identical strings under two keys is how a console ends up with two spellings of one fact the day somebody edits one of them | לא הצלחנו לטעון את רשימת הצוות כרגע. | לא הצלחנו לטעון את רשימת הצוות כרגע. | **SHIPPED — reused** (`he.ts:205`) |
| `floor.empty` | `EmptyState` **title only, no body and no CTA**. Unreachable in practice — the caller is herself a live staff row — so it is a one-line guard against a payload that cannot arrive, and a body would be three sentences written for nobody | אין נשות צוות פעילות | אין נשות צוות פעילות | DRAFTED |
| `floor.sessionEnded` | A tick or a toggle answered **401** and **the loop stopped**. `role="alert"`, one of the three assertive announcements in the feature. The session outlives a shift by design (`session_ttl_seconds = 43200`, no sliding renewal), so the realistic reader is a tablet left on the counter overnight — a plain instruction, not an alarm. Word-for-word the board's sentence, because it is the same fact and the two panels share a screen | תוקף החיבור פג. צריך להתחבר מחדש. | תוקף החיבור פג. צריך להתחבר מחדש. | DRAFTED |
| `floor.accessEnded` | A tick or a toggle answered **403** and the loop stopped — a mid-shift demotion, or an elevated staffer demoted between the last tick and her tap (`design.md` **P-6**). **Deliberately generic** (§0 rule 6): no role is named, nothing is said about what changed, and it does not claim the change is permanent — «כרגע» is doing real work, because a re-promotion restores the panel. Points at a person rather than at a retry, because there is nothing here she can fix from this screen — **and for reception / sales_assistant / seamstress this sentence is the entire product going dark** (`design.md` **F-7**) | אין הרשאה לצפות ברשימת הצוות כרגע. לבירור אפשר לפנות לבעלת הבוטיק. | אין הרשאה לצפות ברשימת הצוות כרגע. לבירור אפשר לפנות לבעלת הבוטיק. | DRAFTED |
| `floor.reload` | The button beside **both** of the two above. Says what it does. On the 401 a reload lands on the login screen; on the 403 it lands on a console whose panel answers 403 again — the honest behaviour of F31's "a demotion bites on the very next request", recorded as F34's **F-10** and inherited, not papered over | רענון הדף | רענון הדף | DRAFTED |

## 6. Errors — one owned string, everything else falls through

**F57 adds no error code** (spec: `SPEC_ERROR_CODES` stays set-equal and empty of new members). Exactly one condition needs copy the shared helper cannot supply, and everything else — including anything unmapped — falls through to `errorMessage(error)`, i.e. to the server's own text.

| Key | Raised by | Approved Hebrew (`he`) | `ar` | Status |
|---|---|---|---|---|
| `floor.error.notFound` | 404 `NOT_FOUND` — a toggle on a colleague deactivated in the gap between the last tick and the tap (or, indistinguishably, another tenant's id, which RLS makes invisible). Renders **inside that card**, `--color-danger`, because a panel-level error names no colleague. Names the **event** that repairs it and never a duration (§0 rule 5) | אשת הצוות הזו כבר לא פעילה. הרשימה תתוקן בעדכון הבא. | אשת הצוות הזו כבר לא פעילה. הרשימה תתוקן בעדכון הבא. | DRAFTED |

**A 403 on a toggle is NOT an error string** — it is terminal and lands in `floor.accessEnded` (§5, `design.md` **P-6**). A 401 likewise. Neither has a row here, and inventing one would produce a card-level message beside a loop that has already stopped.

---

## 7. Register check — the mechanical pass

| Rule | Result |
|---|---|
| Exclamation marks in this deck | **0** |
| Strings claiming, implying or hedging a message send (any tense) | **0** — the feature sends nothing and says nothing about sending |
| Strings claiming the panel is realtime / live / instant | **0** — «עודכן {{time}}» is past tense by construction; «בזמן אמת» appears nowhere |
| Strings naming or implying a **retry interval** (§0 rule 5) | **0** — `staleBody` states what is unknown; `error.notFound` names the next event, not a duration; nothing anywhere says «חמש שניות» |
| Strings naming a **role**, or saying what changed, on the 403 (§0 rule 6) | **0** — `floor.accessEnded` says only that there is no permission, that it is «כרגע», and who to ask |
| Strings for the 2.2.2 mechanism (spec D12) | **8** — `pause` / `pauseAria` / `resume` / `resumeAria` / `pausedAt` / `paused` / `idleStopped` / `resumed`. **At zero the product ships green in CI and non-conformant in law**, because axe has no SC 2.2.2 rule — and this is the second such surface on one screen |
| Emoji, glyphs or icon characters anywhere in a value (§0 rule 7) | **0** — the brief's 🟢/🟡/🔵 ship as «פנויה» / «בהפסקה» inside a `Badge`, and F36's third status will ship as a word too |
| Statuses expressible without their word | **0** — every state carries text: `break` carries the `Badge` word **and** «מאז 11:20» **and** a control reading «חזרה»; `paused` carries «מושהה», a body line and the control's own label flip |
| Strings that blame the staffer | **0** — `staleBody` states what is unknown, the reused `staff.loadFailed` is first-person-plural and unblaming, `sessionEnded` is an instruction |
| Money words | **0** — deposits are E4 |
| Reassurance / encouragement copy | **0** — §0 rule 3 |
| Placeholders, Lorem, `…`-as-content | **0** — the one `…` is inside `floor.loading`, where it is the content |
| `ar` values that are empty strings | **0** — every row carries the Hebrew as its placeholder |
| Keys that overwrite or edit an F51 or F34 key | **0** — four rows are **reused unchanged** and marked SHIPPED; nothing here re-declares or edits an existing value |
| Values for a status the wire cannot carry | **0** — there is no string for `occupied`; F36 ships its word with its writer (spec D9) |
| Strings a poll tick can cause to be **announced** | **0** — six strings ever enter a live region (`loading`, the two break cues, `paused`, `idleStopped`, `resumed`) and none is reachable from a tick: `loading` fires once before any tick, four are the direct consequence of a tap, and the idle stop is the consequence of her *not* tapping. The region is written only when its value changes, so a repaint carrying an unchanged cue produces zero mutation records (F34's **F-7**) |
| Interpolations needing more than one LTR isolation per string | **0** — every interpolated value is a single run. ⚠ **But the helper is chosen per interpolation, not per string, and an earlier draft of this row got it wrong** (`design.md` §9 **F-11**): `{{time}}` and `{{minutes}}` are **numeric** runs and go through the shipped `isolateLtr`, which emits `<bdi dir="ltr">` (`lib/booking.tsx:32-46`). **`{{name}}` does NOT** — it is a display name, and `dir="ltr"` on «נועה לוי» is exactly the bidi defect `design.md` §2.1 bans, *"and it looks deliberate"*. It takes a **bare `<bdi>`**, which needs a two-line `isolateBidi(text, value)` sibling or a `<Trans>`; **one second helper IS invented**, and §6's component table names it beside the cue region. The two `*Aria` keys interpolate `{{name}}` into an `aria-label`, which takes no markup at all and is outside the rule. ⚠ Note also that **F34's shipped cues isolate nothing** — `BoardSection.tsx:385-391` and `:138` interpolate into plain strings — so this panel's isolation is a deliberate divergence from the board, not drift |
