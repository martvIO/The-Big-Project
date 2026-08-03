# Copy deck — F59 Public wall-screen queue board (`apps/storefront`, route `/queue`)

**Date**: 2026-08-03 · **Status**: **DRAFTED under the 2026-07-31 design-gate self-approval** (`LOOP-STATE.md` `rulings_2026_07_31`). The Hebrew is **the user's to edit post-merge** — the F15 P-1 / F33 precedent: a one-line `he.ts` / `ar.ts` edit after merge, never a rebuild. **§5 is the exception and is NOT self-approved**: it is privacy-law text, it stays counsel-gated, and it adds a **fifth counsel item** to the open `in_run_gates` F33 entry.
**Owner of the Hebrew**: the user · **Consumes**: `.planning/specs/public-queue-board.md` (D1–D14) and `design.md` in this directory · **Lands in**: `Frontend/apps/storefront/src/i18n/he.ts` (`document.queueBoard` + a new `queueBoard.*` section + **one amended value in `checkin.*`**) **and `…/i18n/ar.ts`**, same keys, Hebrew standing in untranslated.

**Eight new keys, eight reused, one amended.** The first draft of the spec listed nine new; `queueBoard.retry` is dropped in favour of the shipped `checkin.retry` (**design F-8**).

| | Count | Which |
|---|---|---|
| **New** | **8** | `document.queueBoard` + `queueBoard.{heading, empty, emptyHint, overflow, called, loading, loadFailed}` |
| **Reused from `checkin.*`, not re-declared** | **8** | `pause`, `resume`, `pausedCue`, `resumedCue`, `updatedAt`, `staleAt`, `pausedAt`, `retry` (§4) |
| **Amended** | **1** | `checkin.notice`, in both files — the one privacy-law deliverable in the PR (§5) |
| Deleted | 0 | |

**F59 adds no SMS template, sends no message and touches no `comms_templates.py` body.** There is no §SMS section in this deck and there cannot be one: the board **only reads** and writes nothing, anywhere.

---

## 0. The rules this deck is written under — hard constraints, not preferences

1. **Zero exclamation marks** (pre-decided #5). The product contains none.
2. **Never claim, promise or hedge that a message was sent, in any tense.** Trivially satisfied — F59 sends nothing. ⚠ **And the guard the brief names does not cover this app**: `/נשלח|תישלח|בדרך/` lives at `apps/manage/src/__tests__/i18n.test.ts:452` and walks the **manage** bundle. The storefront's `i18n-keys.test.ts` carries **no register guard at all**, and `apps/storefront/src/i18n/he.ts:38` already ships «הקולקציה בדרך». **This deck complies with the ban anyway** (§7) because it costs nothing; nothing enforces it (**design F-9**).
3. **The board states, it does not reassure.** Every string is a fact. No «הכל תקין», no «מעולה», no encouragement, no apology. A woman reads this screen for an hour from a chair.
4. **Freshness is claimed weakly and honestly.** «עודכן 14:07» says *this was true at 14:07*. Nothing anywhere says «בזמן אמת» or «חי» — the board polls, and a claim it cannot keep even for one interval is worse than the truth.
5. **Nothing on the board is addressed to the room except the one word that calls a specific woman forward.** The heading is a noun phrase, the empty state is a fact, the overflow line is a number. Only `queueBoard.called` speaks to a person, and it speaks to exactly one.
6. **No string names or implies a retry interval.** The client backs off 5s → 60s, so «הלוח יתעדכן בעוד חמש שניות» — the exact sentence a well-meaning editor adds — becomes false as the backoff grows. F34's §0 rule 9, inherited whole.
7. **A count must be grammatical at every value it can take.** The shipped house rule is `apps/manage/src/i18n/he.ts:67-69` — *"Label-then-number, so it is grammatical at every count without four Hebrew plural forms."* This costs one string in §2 and it is **design F-6**.
8. **A row is a place in the queue, never a person.** F33's Ruling 3 means one woman can hold two tickets and render at two positions with the same first name (`app/models/queue_ticket.py:23-26`). Every string that counts must count **places**, because the product cannot count women without a read keyed on `phone` — which `app/db/repositories/queue_tickets.py:15-18` forbids and calls "the security property, not an omission".
9. **The `ar` column is the approved Hebrew, standing in untranslated** (Interview Q3 / pre-decided #47), and it is **never an empty string**: i18next's `returnEmptyString` default renders `""` rather than falling back, so a premature switch would blank the page instead of showing Hebrew. `lng` stays `"he"`, `fallbackLng` stays `"he"`, no switcher ships.
10. **F59 reuses `checkin.*` wherever the two screens say the same thing**, by resolving the same key — never by re-declaring the value. The freshness and pause vocabulary must not diverge between two screens in the same shop. §4 lists all eight.
11. **⚠ No `data-testid`, `className` or any other quoted literal under `apps/storefront/src` may be spelled `queueBoard.…`.** Once `queueBoard` is a section of `he.ts`, `i18n-keys.test.ts:22` scrapes any dotted literal whose first segment is a section name and fails the suite with a confusing "missing from he.ts". The testids are `queue-board`, `queue-board-row`, `queue-board-empty`, `queue-board-overflow`, `queue-board-freshness`, `queue-board-cue`, `queue-board-loading-status`. F33 carried this as its Risk 8; it is now a repeat.

---

## 1. The tab title

| Key | What it must say | Approved Hebrew (`he`) | `ar` (untranslated placeholder) | Status |
|---|---|---|---|---|
| `document.queueBoard` | **One** title for every state of the page, carrying no name and no number. F33 established the rule for the ticket id (`router.tsx:79-82`): a tab strip is read over a shoulder in a shop. Not «התור עכשיו» — «עכשיו» is a liveness claim the poll cannot keep, and a title has no freshness line beside it to qualify it. Not «מקומך בתור», which is taken by `/q/{ticket_id}` and would make two different screens indistinguishable in a tab strip | לוח התור | לוח התור | DRAFTED |

## 2. The board

| Key | What it must say | Approved Hebrew (`he`) | `ar` | Status |
|---|---|---|---|---|
| `queueBoard.heading` | The page's single `h1`. **A statement of fact that stays true in both worlds** (spec D10(1)): before F58 the rows are `status = 'waiting'`, after F58 they are women who are waiting. Not «התור» alone (a bare noun that could name the shop's queueing policy), not «מי בתור» (a question the board does not ask), not «הבאות בתור» — that implies an order of service the product cannot promise until F58 stamps `called_at` | ממתינות בתור | ממתינות בתור | DRAFTED |
| `queueBoard.overflow` | Rendered only when `waiting_total > entries.length`, with the number computed as `waiting_total − entries.length` and **never echoed**. **⚠ REVISED from the spec's «ועוד {{count}} ממתינות» — design F-6, and there are two independent reasons.** (1) **Grammar**: the count is 1 the moment a sixth ticket exists, and «ועוד 1 ממתינות» needs the singular «ממתינה» — §0 rule 7's house rule exists for exactly this. «בתור» does not inflect for number, so «ועוד 1 בתור» and «ועוד 35 בתור» are both grammatical. (2) **Truth**: under Ruling 3 the quantity counts **tickets**, so «ממתינות» names women the product cannot count (§0 rule 8); «בתור» counts places in a queue, which is precisely what `waiting_total` is. **This refines spec D10 on an axis D10 did not consider** — D10 ruled on arrivals-vs-waiters and resolved it with the deployment gate; the ticket-vs-woman axis survives F58's merge window. D10's ruling stands, «נרשמו היום» stays declined, and this is one string in two files to overturn | ועוד {{count}} בתור | ועוד {{count}} בתור | **REVISED** — `{{count}}` renders inside `<bdi dir="ltr">` |

**`{{count}}` and i18next's plural machinery.** Called as `t("queueBoard.overflow", { count })`, i18next looks for `overflow_one` / `overflow_other` before falling back to the base key. The shipped precedent is `apps/manage/src/components/BoardSection.tsx:603` doing exactly this against `board.truncated`, so the fallback is known to work in this codebase. Noted so that a future translator who adds a suffixed variant knows it will start being selected.

## 3. The row

| Key | What it must say | Approved Hebrew (`he`) | `ar` | Status |
|---|---|---|---|---|
| `queueBoard.called` | Beside the name on a row whose `called === true` — **the word that keeps the highlight out of SC 1.4.1's colour-alone failure** (design §2.2), alongside an 8px `gold-strong` rule and a `bg-surface` field. Feminine singular imperative, because it addresses exactly one woman by the name printed beside it. **A separate key from the shipped `checkin.called` («אפשר לגשת לדלפק») rather than a reuse**, and the reason is register plus width: F33's string is *permission granted to the holder on her own phone*, and at 59px in a row beside a number and a name it is roughly 590px of type where nine characters fit. **⚠ Unreachable until F58 ships** — nothing in the product writes `called_at`, so this string renders only against a stubbed API client (spec D10) | גשי לדלפק | גשי לדלפק | DRAFTED |

## 4. Freshness and the SC 2.2.2 control — eight keys, all SHIPPED and REUSED

**F59 declares none of these.** They resolve from `checkin.*` exactly as they do from `QueuePositionPage.tsx`, and `i18n-keys.test.ts` resolves `"checkin.pause"` out of `QueueBoardPage.tsx` identically. Listed in full because a reader checking this deck against the rendered screen must find the reason, not a gap — and because **a build that re-declares any of them into `queueBoard.*` ships a second spelling of the same sentence in the same shop.**

| Key | Where it renders on the board | Approved Hebrew (`he`) | `ar` | Status |
|---|---|---|---|---|
| `checkin.updatedAt` | The freshness line, live. Past tense by construction | עודכן | עודכן | **SHIPPED — reused** — followed by the time in its own `<bdi dir="ltr">` |
| `checkin.staleAt` | The freshness line after a failed tick, a 429 or a flooder holding the budget spent. **The rows stay on screen and stay correct as of that time** | העדכון האחרון היה | העדכון האחרון היה | **SHIPPED — reused** |
| `checkin.pausedAt` | The freshness line while the loop is stopped. **Paused beats stale** — a stopped loop cannot fail a tick | העדכון מושהה. עודכן | העדכון מושהה. עודכן | **SHIPPED — reused** |
| `checkin.pause` | The control's visible label — and its accessible **name**, because there is no `aria-label` | השהיית העדכון | השהיית העדכון | **SHIPPED — reused** |
| `checkin.resume` | The same control once paused. **One button whose name flips**, never two buttons and never `aria-pressed` | חידוש העדכון | חידוש העדכון | **SHIPPED — reused** |
| `checkin.pausedCue` | Announced **once** through the `queue-board-cue` region on press | העדכון האוטומטי הושהה | העדכון האוטומטי הושהה | **SHIPPED — reused** |
| `checkin.resumedCue` | Announced once on resume. Needed for a real reason and not for symmetry: a screen reader does not reliably re-announce the name of an **already-focused** control that renamed itself under the press, so without it the confirmation a sighted user gets free is denied to the user 2.2.2 exists for | העדכון האוטומטי חודש | העדכון האוטומטי חודש | **SHIPPED — reused** |
| `checkin.retry` | The error arm's button. **⚠ Reused rather than minting `queueBoard.retry`** — same word, same act, and §0 rule 10 is the same principle that reuses the seven above (**design F-8**). The spec's Frontend-changes table lists `retry` under `queueBoard`; a builder following it literally ships a ninth key duplicating a shipped value | ניסיון נוסף | ניסיון נוסף | **SHIPPED — reused** |

**Three distinguishable SENTENCES, not one sentence and a colour.** With one string, user-paused and backed-off-stale would differ only by a class — "status signalled by colour alone", reproduced inside the rule against it. The frontend test asserts them with `toHaveTextContent`, never with `toHaveClass`.

**⚠ And on this screen the colour escalation does NOT come across** (design **F-7**). `QueuePositionPage.tsx:305` renders paused and stale in `font-semibold text-warning-text`; on a panel that drops the page's only honesty line from **15.24:1 to 5.70:1** at the exact moment it matters most. `font-semibold` stays; `text-ink` stays; the sentences carry the state.

## 5. States

| Key | What it must say | Approved Hebrew (`he`) | `ar` | Status |
|---|---|---|---|---|
| `queueBoard.loading` | Carried by the `VisuallyHidden role="status"` region on the **first** load only; the region unmounts on the first settled response. Feminine plural, matching the two shipped storefront loading strings it sits beside (`checkin.loading` «טוענות את פרטי הבוטיק», `checkin.positionLoading` «טוענות את מקומך בתור»). No trailing «…» — no shipped storefront loading string carries one | טוענות את לוח התור | טוענות את לוח התור | DRAFTED |
| `queueBoard.empty` | **The state the screen is in for most of the day, rendered at the position-number scale (75.6px, legible beyond 5m) and centred** — a designed state, never a blank page and never an error (design §4, `W-empty`). A fact, not a fault: not «אין מה להציג» (which describes the software), not «התור ריק» (blunt, and it reads as a fault on a wall in a shop with customers in it). **«כרגע» is qualified by the freshness line beside it**, which is exactly why the freshness line is in the empty state at all — without it, an empty board is indistinguishable from a crashed board | אין כרגע ממתינות | אין כרגע ממתינות | DRAFTED |
| `queueBoard.emptyHint` | Under it, at the name scale (59px, ~3.9m) — **room-legible on purpose, because telling a walk-in what to do is the one genuinely useful thing an empty board can say.** Names no physical location: the QR sign is a printed artefact the boutique places wherever it likes, and «בכניסה» or «ליד הדלת» would be a claim about the world the product cannot keep. **No CTA button** — there is nothing on this screen to press and the action happens on her own phone | אפשר להצטרף לתור בסריקת הקוד שבבוטיק. | אפשר להצטרף לתור בסריקת הקוד שבבוטיק. | DRAFTED |
| `queueBoard.loadFailed` | The **first** request failed and nothing ever loaded. `role="alert"`, **at the name scale**, because the room must be able to tell a broken board from an empty one — a blank screen reads as «אין ממתינות» and a woman acts on it. The outage register: recoverable, unblaming, no technical words, no status code. The exact shape of the shipped `checkin.loadFailed` («לא הצלחנו להציג את מקומך בתור כרגע.») because it is the same failure on the neighbouring screen. **The loop keeps running underneath** (spec D9 — no terminal), so nothing here promises a retry and nothing needs to | לא הצלחנו להציג את לוח התור כרגע. | לא הצלחנו להציג את לוח התור כרגע. | DRAFTED |

**No string for a 404, a 429 or a 5xx separately.** All three land in `queueBoard.loadFailed` if nothing has ever loaded and in `checkin.staleAt` if something has. F59 introduces **no error code and no handler** — `SPEC_ERROR_CODES` for this surface is `{TENANT_NOT_FOUND, TOO_MANY_ATTEMPTS}`, a subset of the four already pinned — so `errorMessageKey` (`api.ts:48-77`) gains no `case`.

**No «הבאה בתור», no wait-time string, no "now serving".** Spec D10(1) and pre-decided #28. Until F58 ships, position 1 is *the first person who arrived today*, not the next person to be seen.

---

## 6. ⚠ The collection notice — the one privacy-law change, and it is COUNSEL-GATED

**This is the only string in the PR that is not the user's to edit casually, and the only deliverable in the feature that has no test unless A32b is written correctly.**

`checkin.notice` (`he.ts:423`, `ar.ts:86`) is shipped, counsel-gated **interim** Hebrew whose own header comment says *"F20 replaces both VALUES, here and in `ar.ts`, and that is the whole swap: no component may hardcode any part of either sentence."* That value was true when F33 shipped. **F59 makes it incomplete**: the first word of her name is now published on an unauthenticated URL. Amendment 13 requires notice **at the moment of collection**, and the moment of collection is `/checkin`.

**⚠ The clause names a PUBLIC WEB PAGE, not "a screen in the boutique".** A notice describing in-store display when the processing is worldwide publication is not merely incomplete — it is **affirmatively narrower than the truth at the moment of collection**, which is worse than the current silence, because it becomes an express representation she can rely on. And it says *the first word of the name you entered*, **never** "your first name and not your surname": D5's derivation is `name.split()[0]`, and «כהן נועה» is ordinary Israeli form-filling that returns «כהן». **The notice must not claim more than the code delivers.**

### Before → after (the whole diff, both files)

**Before** — `he.ts:423-424` and `ar.ts:86-87`, identical:

> הפרטים שאת ממלאת כאן נשמרים אצל {{boutique}} לצורך ניהול התור בלבד — לשמור את מקומך ולקרוא לך כשיגיע תורך — ונמחקים כמה ימים לאחר הביקור. **הם** לא ישמשו לפניות שיווקיות אלא אם סימנת את התיבה שלמטה; אם סימנת אותה, השם ומספר הטלפון יישמרו לצורך זה עד שתבקשי להסיר את ההסכמה.

**After** — one clause inserted, one pronoun made explicit:

> הפרטים שאת ממלאת כאן נשמרים אצל {{boutique}} לצורך ניהול התור בלבד — לשמור את מקומך ולקרוא לך כשיגיע תורך — ונמחקים כמה ימים לאחר הביקור. **מקומך בתור והמילה הראשונה בשם שהזנת מוצגים בלוח התור של הבוטיק — עמוד אינטרנט ציבורי שכל מי שיודע את כתובת האתר של הבוטיק יכול לפתוח, ולא רק מסך שנמצא בתוך החנות. מספר הטלפון שלך לא מוצג שם.** **הפרטים** לא ישמשו לפניות שיווקיות אלא אם סימנת את התיבה שלמטה; אם סימנת אותה, השם ומספר הטלפון יישמרו לצורך זה עד שתבקשי להסיר את ההסכמה.

| | |
|---|---|
| **Key** | `checkin.notice` — **amended, not replaced**; the slot and its `{{boutique}}` interpolation are untouched |
| **`ar`** | The identical amended Hebrew, untranslated (§0 rule 9) |
| **Status** | **INTERIM · COUNSEL-GATED · the `in_run_gates` F33 entry STAYS OPEN and gains a fifth item** |

**What the clause says, and what it deliberately does not:**

| Says | Does not say |
|---|---|
| her **place in the queue** is shown on the boutique's queue board | that her surname is not shown — **a promise D5 cannot keep** (design §4, «כהן נועה») |
| **the first word of the name she entered** is shown | "her first name" |
| the board is **a public web page anyone who knows the boutique's web address can open** | "a screen in the boutique" |
| **and not only a screen inside the shop** | anything about who else may be looking |
| her **phone number is not shown there** | a retention period for the board (it holds nothing; it reads) |

**⚠ F-12 — «הם» must become «הפרטים», and that is a required collateral edit rather than an optional tidy.** The insertion puts «מספר הטלפון שלך» between «הפרטים» and the pronoun, making «הם לא ישמשו לפניות שיווקיות» read as *the phone number will not be used*. The meaning is identical after the fix and the sentence is grammatical again. **The alternative — appending the clause after the marketing sentence to preserve the pronoun — was weighed and declined**: it buries the one new processing this feature adds behind the consent text, in the one place Amendment 13 requires prominence.

**The fifth counsel item, phrased so counsel is asked the right question:**

> ***What must the notice say about a first name published on a public, unauthenticated web page?***

**Not** "displayed on a public screen", which invites an answer about signage. Beside the four already open (the boutique, the purpose, the retention window, and the opted-in-data exception).

**One tension recorded rather than resolved here, because it is counsel's:** the shipped sentence promises «לצורך ניהול התור **בלבד**». Post-F58 the board is queue management; pre-F58 it publishes the names of women who left hours ago, which is why spec D10(4) says the board **is not deployable to a customer-facing wall until F58 ships**. F59 adds a clause and does **not** rewrite the purpose limitation — that is exactly what the fifth counsel item is for.

**⚠ The amendment needs its own assertion, and the obvious one cannot fail.** `CheckinPage.test.tsx:297-306` renders `t("checkin.notice", { boutique })` and compares against the same bundle, so it passes **byte-identically against the unamended value**. It stays green and proves nothing about D13.

| Criterion | Assertion |
|---|---|
| **A32a** | `CheckinPage.test.tsx:297-306` is **unchanged and still green** — the amendment adds a clause and does not touch the interpolation |
| **A32b** | **`he.translation.checkin.notice` and `ar.translation.checkin.notice` each contain `"עמוד אינטרנט ציבורי"`** — asserted **against the resource bundle, never through `t()`**, in the style `i18n-keys.test.ts` already uses to read `he.ts` values directly. One `expect` each. **This is the only assertion in the PR that fails the moment D13 is forgotten or reverted.** |

**Declined: shipping the board without touching the notice.** It would leave a shipped sentence describing a narrower use of her data than the product performs, in the one place the law requires the description to be accurate, on the one surface where the disclosure is to strangers. **Declined: a privacy notice on the board itself.** The board collects nothing from the people reading it, and it would spend rows on reassurance theatre. **Declined: F20's per-boutique override and any final wording** — that is the Q1 user-only class, and F59 declines it exactly as F33 did.

---

## 7. Register check — the mechanical pass

| Rule | Result |
|---|---|
| Exclamation marks in this deck | **0** |
| Strings claiming, implying or hedging a send (`/נשלח|תישלח|בדרך/`) | **0** — and the ban is complied with **voluntarily**: it lives in `apps/manage`, walks the manage bundle, and the storefront's own `he.ts:38` already ships «הקולקציה בדרך». Nothing enforces it here (**design F-9**) |
| Strings claiming the board is realtime / live / instant | **0** — «בזמן אמת» and «חי» appear nowhere; every freshness lead is past tense; `document.queueBoard` is «לוח התור» and not «התור עכשיו» for exactly this reason |
| Strings naming or implying a **retry interval** | **0** — §0 rule 6. The loop has no terminal and backs off to 60s, and no string mentions either |
| Counts that are ungrammatical at any value they can take | **0** — one string was **revised** (§2). «ועוד 1 בתור» / «ועוד 35 בתור» are both grammatical; «ועוד 1 ממתינות» is not, and 6 waiting tickets is an ordinary Tuesday |
| Strings that count **women** rather than **places** | **0** — §0 rule 8. Under Ruling 3 the product cannot count women without a read keyed on `phone`, which `queue_tickets.py:15-18` forbids |
| Strings the board renders about a **specific person** | **1** — `queueBoard.called` «גשי לדלפק», which is the entire point of the highlight, and it is **unreachable until F58** |
| Strings for the SC 2.2.2 mechanism | **8, all reused, none re-declared** (§4). At zero the product ships green in CI and non-conformant in law, because axe has no 2.2.2 rule |
| Strings that promise the surname is withheld | **0** — §6's clause says *the first word of the name you entered*, and design §4's «כהן נועה» row is why |
| Strings that describe the board as in-store only | **0** — §6's clause names the public web page explicitly, which is the defect D13 exists to correct |
| Strings that blame the visitor | **0** — `loadFailed` is first-person-plural and unblaming; `empty` is a fact |
| Money words | **0** — deposits are E4 |
| Reassurance / encouragement copy | **0** — §0 rule 3 |
| Placeholders, Lorem, `…`-as-content | **0** — the only «…» in the feature is D5's **server-side** truncation ellipsis, which is data rather than copy |
| `ar` values that are empty strings | **0** — every row carries the Hebrew as its placeholder, including §6's amended notice |
| Keys that overwrite or edit an **F33** key | **1, deliberately** — `checkin.notice`, which exists to be swapped and whose own comment says so (§6). The other eight `checkin.*` keys are **resolved**, never re-declared |
| Quoted literals spelled `queueBoard.…` outside `he.ts`/`ar.ts` and a `t()` call | **0 required** — §0 rule 11. The testids are `queue-board-*` |
| Strings a poll tick can cause to be **announced** | **0** — only two strings ever enter a live region (`checkin.pausedCue`, `checkin.resumedCue`), both are the direct consequence of a press, and **the board announces no content at all** — deliberately unlike `QueuePositionPage.tsx:144-149`, because this screen is about other people and «מיכל, גשי לדלפק» into a stranger's screen reader is both noise and a broadcast she did not agree to |
| Interpolations needing more than one LTR isolation per string | **0** — `queueBoard.overflow` carries one `{{count}}`; the freshness leads carry none and the call site appends the time in its own `<bdi dir="ltr">` |
