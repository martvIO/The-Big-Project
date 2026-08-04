# Copy deck — F60 per-page guided walkthrough (`apps/manage`: the «מדריך» trigger, the step dialog, 36 steps across fourteen sections · `apps/storefront`: one disclosure on `/checkin`)

**Date**: 2026-08-04 · **Status**: **DRAFTED under the approved register, self-approved with the design gate.** The 2026-07-31 ruling named two novel interaction patterns for this run and F60 is neither, so there is no prototype and no `design-critic` pass. **The gate goes away; this deck does not.** **The Hebrew remains the user's to edit post-merge** — the F15 P-1/P-5, F34, F57, F36 and F37 precedent: a one-line `he.ts` / `ar.ts` edit after merge, never a rebuild. Console copy and one public orientation sentence, no counsel gate (⚠ **and §0 rule 3 is what keeps it that way**) · **Owner of the Hebrew: the user**
**Consumes**: `.planning/specs/guide-walkthrough.md` (**D1** for the section inventory and step counts, **D8** for the namespace) · `design.md` in this directory (**§2.4** for the counter, **§6.4** for the storefront fence, **§10 F-3/F-4** for two corrections) · the **fourteen section components as shipped**, which for four of them is the only place their words exist (rule 4)
**Lands in**: `frontend/apps/manage/src/i18n/he.ts` (a new flat `guide.*` namespace) **and `…/i18n/ar.ts`**, same keys, the approved Hebrew standing in untranslated · `frontend/apps/storefront/src/i18n/he.ts` and `ar.ts`, **two keys under the existing `checkin` section**

**THIS DECK IS CANONICAL.** `design.md`'s inline Hebrew is illustrative and says so. Where a string here differs from the spec or from a diagram, **this file is the value that ships**, and every such divergence is marked ⚠ in its own row.

**43 console keys invented, 0 reused. 2 storefront keys invented, 0 reused.** ⚠ **Zero reuse is a decision, not an oversight** — see §5. And **there is no `guide.triggerAria`** (DL20): the trigger's accessible name is its visible «מדריך», which makes WCAG 2.5.3 true by construction here and costs `i18n.test.ts` no 2.5.3 loop.

---

## 0. The rules this deck is written under — hard constraints, not preferences

1. **Zero exclamation marks** (pre-decided #5). Mechanically checked — `i18n.test.ts` filters every value in `HE` for `"!"`. Instructional copy has no reason to reach for one; §4 is the scan.
2. ⚠ **Never claim, promise or hedge that a message was sent, in any tense.** `i18n.test.ts` enforces `/נשלח|תישלח|בדרך/` over every value in `HE`. **`guide.bookings.3` is this deck's one string at genuine risk** — "what the customer is told about a reschedule" is a sentence about messaging — and it is resolved by wording rather than by dodging: the row says what the console **records**, and says out loud that the console is not evidence of what reached her handset. That is also the true statement, which is why it is the easy fix rather than the clever one.
3. ⚠ **No string states a data-handling fact.** The console rows describe screens; the storefront's two rows describe **the queue** — what checking in puts her into, what she gets back, and that a staffer calls her. `CheckinPage.tsx:299-302` rules directly against the alternative (*"never behind a disclosure: notice at the moment of collection means visible at the moment of collection"*), and a second notice at the same collection point would **void this spec's Gate 1 self-approval** ("no privacy-law text"). `checkin.notice` and `checkin.optIn` are untouched. **If the intended content genuinely is data handling, the feature stops for the user** (DL15).
4. ⚠ **Every step was written with its section component open, and FOUR of the fourteen sections have no i18n at all.** `grep -c useTranslation` returns **0** for `HoursSection.tsx`, `TypesSection.tsx`, `TermsSection.tsx` and `CatalogSection.tsx` — their Hebrew is hardcoded in the component. A writer working from `he.ts` invents labels those four screens do not use. Every row below that quotes an on-screen label cites the file and line the label lives in, and **a quoted label is byte-identical to the shipped one or it is not quoted.**
5. **A step names no control the reader may not have.** Two sections gate controls *inside* themselves — `TermsSection.tsx:20` (`const isOwner = role === "owner"`) hides the publish form from a shift manager, and `AtelierSection.tsx:1344-1356` (`mayWork = elevated || (isSeamstress && (mine || unassigned))`) gives a seamstress no controls at all on a colleague's ticket. Both are handled **in the copy**, by describing the section rather than promising a button (DL7). The two rows carry a ⚠.
6. ⚠ **A step names no section the reader cannot reach.** The structural gate (`activeKey`) guarantees she is looking at a section she can open; it guarantees nothing about a section a *sentence* points at. Caught twice below: `guide.board.3` does **not** say «הצוות בקומה» (a `FLOOR_ONLY` nav row an owner never sees) and `guide.profile.3` does **not** say «סליקה ותשלומים» (owner-only). Both describe the thing instead of naming the door.
7. **The screens state, they do not reassure.** No «מצוין», no «קל מאוד», no «אל דאגה», no second person plural cheer. A boutique owner reading a walkthrough wants a fact per sentence.
8. **One sentence per step**, and the em-dash carries the subordinate clause. Longer than one sentence and the live region reads two utterances for one step change; shorter and the step is a label, not help.
9. **No string names a duration, an interval or a threshold.** `usePoll`'s backoff stretches 5s → ~60s, so any number is true at tick 1 and false by tick 5. `guide.board.3` names the **event** («עודכן»), never a rate.
10. **No digit at a string edge and no digit adjacent to a neutral.** Only `guide.progress` carries digits, and §1 records why its trailing «במדריך» is load-bearing.
11. **The `ar` column is the approved Hebrew standing in untranslated** (Interview Q3 / pre-decided #47 / the 2026-07-31 languages ruling) and is **never an empty string**: i18next's `returnEmptyString` default renders `""` rather than falling back, so a premature switch would blank the dialog instead of showing Hebrew. `lng` stays `"he"`, `fallbackLng` stays `"he"`, no switcher ships. The assertion is `ar[key] === he[key]` — **not "non-empty"**, which passes on an English string, a `TODO`, or a *different* Hebrew wording.
12. **Every value is a real string.** No `…`-as-placeholder, no Lorem, nothing to be filled in later. ⚠ **R6 is the standing version of this rule**: whoever adds a fifteenth `SectionKey` gets a type error in `guide.ts` and will be tempted to silence it with a placeholder sentence. **A placeholder is a lie with a compile-time blessing** — the type buys a prompt, not a guarantee.

### 0.1 ⚠ The one test edit this deck depends on, and rules 1 and 2 are void without it

`i18n.test.ts` selects each feature's flat keys with its own constant and **folds them into one `HE` array**. `HE_F60` must be **folded in, not merely declared** — the file says so about itself: *"Folded in, not just declared: without this the resolve check, BOTH register guards and the `ar` parity guard silently skip every F52 key."*

```ts
const HE_F60 = entries(he.translation, (key) => key.startsWith("guide."));
const HE = [ …existing constants…, ...HE_F60 ];
```

⚠ **Read the FOLD, never a line number** — the array grows every time a feature lands.

**No `nav.` term in the selector, and that is an assertion rather than an omission.** Every other feature's constant opens `key === "nav.x" || …`; this one does not, because F60 adds **no nav row** — `SectionKey` stays fourteen, `NAV` stays fourteen, `Nav.test.tsx` needs no edit. `guide.trigger` is a header control, not `nav.guide`.

**Give the block its own floor**: `expect(HE_F60.length).toBeGreaterThanOrEqual(43)`. Folded into an existing list without one, this feature's rows could shrink by 43 and still pass.

**And its own `ar` VALUE-parity guard**, in the shape of the three shipped twins (`HE_F36`, `HE_F58`, `HE_F37`): `HE_F60.filter(([k, v]) => arTranslation[k] !== v)` must be `[]`.

⚠ **The console's `i18n.test.ts` has NO source scanner** (that is the storefront's `i18n-keys.test.ts`). A `guide.*` key that exists in `he.ts` and is never rendered passes the floor, both register guards and the parity guard. **The only thing between this deck and a dead key is `GUIDE_STEPS`' literal list and `GuideOverlay.test.tsx` §1's set equality** — which is spec R7, and is why §4 below counts the rows by hand.

---

## 1. Chrome — 7 keys

| Key | What it must say | `he` | `ar` (untranslated) | Status |
|---|---|---|---|---|
| `guide.trigger` | The header button. One word, because it sits beside «יציאה» in a chrome row and anything longer reads as an action. **«מדריך» and not «עזרה»**: help is what you want when something is broken, and nothing here is broken — this is the manual, opened deliberately. It is also the word LOOP-STATE's ruling uses | מדריך | מדריך | DRAFTED |
| `guide.title` | The dialog's `<h2>`, and its `aria-labelledby` target. `{{section}}` is the **already-translated nav label**, so no section name is transcribed twice and a nav-label edit never desynchronises the guide. ⚠ **No `<bdi>` and no isolate**: all fourteen labels are pure Hebrew (`he.ts:14-20` and the nine flat `"nav.*"` literals), so there is no run to reorder — unlike `{{name}}`, which always takes one | מדריך — {{section}} | מדריך — {{section}} | DRAFTED |
| `guide.progress` | The step counter, above the step. ⚠ **The trailing «במדריך» is load-bearing twice and is a correction — see §6 C-1.** (a) It keeps **both digits between Hebrew words**, which is D5's bidi rule; without it `{{total}}` sits at the string edge. (b) The live region utters this **alone**, with no chrome around it, so one word naming which of the console's `role="status"` regions is speaking is the `floor.idleStopped`-vs-`board.idleStopped` argument applied here. ⚠ **`isolateLtr` is NOT the alternative**: it splits on `indexOf` (`lib/booking.tsx:76`), so on «שלב 3 מתוך 3» it isolates the FIRST 3 and leaves the trailing one bare — on the most-visited step | שלב {{step}} מתוך {{total}} במדריך | שלב {{step}} מתוך {{total}} במדריך | DRAFTED |
| `guide.next` | The primary, on every step but the last. Bare and directional; the console's shortest possible forward verb | הבא | הבא | DRAFTED |
| `guide.prev` | The secondary, **absent on step 1 rather than disabled** (DL10). The exact mirror of `guide.next`, one word, so the pair reads as one axis | הקודם | הקודם | DRAFTED |
| `guide.done` | Replaces `guide.next` on the last step, in the same position. **«סיום» and not «סגירה»**: it says *you have reached the end*, which «סגירה» does not — and the two must differ, because they sit side by side in the same footer | סיום | סיום | DRAFTED |
| `guide.close` | The persistent ghost dismiss, **on every step** (DL19). ⚠ **A new key rather than a reuse of `rooms.cancel` («ביטול»), and the reason is register.** `SosRaiseDialog:196-201` reuses «ביטול» because it is dismissing **an action in progress**; a walkthrough has no action in progress, so «ביטול» reads as *cancel what?* **This is the only pointer route out of the dialog** — `Modal` binds no backdrop click and the chrome has no X — so on a boutique tablet with no Esc key it is the whole exit | סגירה | סגירה | DRAFTED |

---

## 2. The steps — 36 keys, one table per section, in `NAV` order

**Fourteen sections, derived from the shipped `App.tsx:24-41` + `:83-152` on 2026-08-04 — not from any document.** Role sets: `ALL = [owner, shift_manager]` · `FLOOR_ONLY = [reception, sales_assistant, seamstress]` · `ATELIER_ROLES = [owner, shift_manager, seamstress]`.

### 2.1 `dashboard` — «סקירה» · ALL · 2 steps

| Key | Verified against | `he` | `ar` | Status |
|---|---|---|---|---|
| `guide.dashboard.1` | `DashboardSection.tsx:13-17` (two spans, nothing bridges them) · `dashboard.forwardHeading`, `dashboard.weeksHelp`, `dashboard.forwardHelp` — every number ships its own help line | המסך מציג שני טווחים נפרדים — תפוסה בשבעת הימים הקרובים, ומתחתיו סיכום של שבועות שכבר הסתיימו — ומתחת לכל מספר יש שורה שמסבירה מה בדיוק נספר בו. | *(identical)* | DRAFTED |
| `guide.dashboard.2` | `DashboardSection.tsx:10-13`: *"It has NO interactive control of any kind — no picker, no filter, no retry, no link, no row that opens anything."* The step states that as a fact instead of letting her hunt for one | אין כאן מה לשנות ואין על מה ללחוץ — מספר שנראה לא נכון נבדק במסך שממנו הוא הגיע, למשל «תורים» או «שעות פעילות». | *(identical)* | DRAFTED |

### 2.2 `profile` — «פרופיל והגדרות» · ALL · 3 steps

| Key | Verified against | `he` | `ar` | Status |
|---|---|---|---|---|
| `guide.profile.1` | `profile.publicNotice` («השדות האלה מופיעים בדף הפומבי של הבוטיק») + `manage-restyle.md`'s note that F10 made `phone`/`address`/`description`/`maps_url` world-readable **and a home-based owner had typed her home address into a field that had only ever been private**. That is the one thing this step exists for | החלק העליון, «פרופיל הבוטיק», הוא מה שהלקוחות רואות בדף הפומבי — טלפון, כתובת, קישור למפות ותיאור — ולכן כתובת שאינה מיועדת לפרסום לא נכתבת כאן. | *(identical)* | DRAFTED |
| `guide.profile.2` | `profile.bridesOnly` + `profile.bridesOnlyHint` («כל סוגי התורים יוצגו לכלות בלבד») | המתג «בוטיק לכלות בלבד» מסמן את כל סוגי התורים כמיועדים לכלות, ומשנה את מה שהלקוחה רואה כשהיא בוחרת סוג תור. | *(identical)* | DRAFTED |
| `guide.profile.3` | `profile.depositsEnabled` + `gateway.depositsWithoutGateway` («גביית מקדמות מופעלת בהגדרות, אבל אין חשבון סליקה מחובר») ⚠ **rule 6**: it does **not** name «סליקה ותשלומים», which is an owner-only nav row a shift manager reading this step cannot open | המתג «גביית מקדמות מופעלת» נשמר כאן, אבל מקדמה תיגבה בפועל רק אחרי שחשבון הסליקה של הבוטיק יחובר. | *(identical)* | DRAFTED |

### 2.3 `hours` — «שעות פעילות» · ALL · 3 steps

⚠ **No i18n in this component** (rule 4). Every quoted label is from `HoursSection.tsx`.

| Key | Verified against | `he` | `ar` | Status |
|---|---|---|---|---|
| `guide.hours.1` | `HoursSection.tsx:172-195` — the weekly grid's four column labels «יום», «פתיחה», «סגירה», «קיבולת», Sunday-first (`:9`) | הטבלה העליונה היא השבוע הקבוע — לכל יום שעת «פתיחה», שעת «סגירה» ומספר תורים מקבילים בעמודת «קיבולת» — והיא זו שמייצרת את המועדים שהלקוחה רואה. | *(identical)* | DRAFTED |
| `guide.hours.2` | `HoursSection.tsx:245-269` — «תאריך», «סגור כל היום», «פתיחה», «סגירה», «הערה»; `:322` «הסרת תאריך חריג» | תאריך חריג הוא חריגה חד־פעמית מהשבוע הקבוע — יום «סגור כל היום», או יום עם שעות אחרות — ומוסיפים אותו למטה, בנפרד מהטבלה. | *(identical)* | DRAFTED |
| `guide.hours.3` | The one thing an owner gets wrong here. Consistent with `booking.rescheduleTitle`'s existence: a booked appointment moves only when a person moves it. ⚠ **rule 6 is satisfied**: «תורים» is `roles: ALL`, so both readers of this step can open it | שינוי כאן משפיע על מועדים שעדיין אפשר להזמין ולא על תור שכבר נקבע — תור קיים נשאר במקומו עד שמישהי מזיזה אותו במסך «תורים». | *(identical)* | DRAFTED |

### 2.4 `types` — «סוגי תורים» · ALL · 3 steps

⚠ **No i18n in this component** (rule 4). Labels from `TypesSection.tsx`.

| Key | Verified against | `he` | `ar` | Status |
|---|---|---|---|---|
| `guide.types.1` | `TypesSection.tsx:77-91` («שם», «משך (דקות)», «קהל יעד») and `:257` (the two audience words «כלות בלבד» / «כולם») | סוג תור קובע כמה זמן הפגישה נמשכת ולמי היא מוצעת — «כלות בלבד» או «כולם» — וזה מה שהלקוחה בוחרת כשהיא מזמינה. | *(identical)* | DRAFTED |
| `guide.types.2` | `TypesSection.tsx:101` («נדרשת מקדמה») and `:106` («מקדמה (₪)»), both quoted byte-identically. ⚠ **«מקדמה» throughout this deck** — see §6 C-2 on the shipped «מקדמה»/«פיקדון» split | אם מסומן «נדרשת מקדמה», הסכום בשדה «מקדמה (₪)» הוא הסכום לסוג הזה בלבד, ולכל סוג יכול להיות סכום אחר. | *(identical)* | DRAFTED |
| `guide.types.3` | `TypesSection.tsx:113` («סדר תצוגה») and `:309` («העברה לארכיון»). ⚠ It says archived-not-deleted and **stops there** — the earlier draft explained *why* (old bookings keep their type name), which is a mechanism this deck did not verify and would be asserting on the server's behalf | השדה «סדר תצוגה» קובע את הסדר שבו הסוגים מופיעים בפני הלקוחה, וסוג שכבר לא בשימוש עובר «העברה לארכיון» ולא נמחק. | *(identical)* | DRAFTED |

### 2.5 `terms` — «מדיניות ביטולים» · ALL · 2 steps

⚠ **No i18n in this component** (rule 4). ⚠ **`TermsSection.tsx:20` hides the publish form from a shift manager** — rule 5 applies to step 2 and it is the sharpest case in the deck: eleven of a shift manager's rows are fine and this is the one that could lie.

| Key | Verified against | `he` | `ar` | Status |
|---|---|---|---|---|
| `guide.terms.1` | `manage-restyle.md`'s *immutable-ledger look* — history rows with «גרסה N» + created date, *"NO edit affordance anywhere"*; `TermsSection.tsx:128-144` («החזר מלא עד (שעות לפני התור)», «אחוז חילוט מחוץ לחלון», «תוכן מדיניות הביטולים») | מדיניות הביטולים נשמרת בגרסאות — כל גרסה נשמרת עם התאריך שבו נוצרה, ואף גרסה אינה נערכת ואינה נמחקת אחרי שנוצרה. | *(identical)* | DRAFTED |
| `guide.terms.2` | ⚠ **Rule 5.** Describes versioning and names the act as **the owner's**, rather than pointing at a «שמירת גרסה חדשה» form a shift manager does not have. Consistent with the section's own shift-manager line, `TermsSection.tsx:102`: «יש לפנות לבעלת הבוטיק כדי להגדיר מדיניות ביטולים.» | לקוחה שהזמינה תור מחויבת לגרסה שהייתה בתוקף באותו רגע, ולכן גרסה חדשה חלה על הזמנות חדשות בלבד — ויצירת גרסה חדשה היא פעולה של בעלת הבוטיק. | *(identical)* | DRAFTED |

### 2.6 `catalog` — «שמלות» · ALL · 3 steps

⚠ **No i18n in this component** (rule 4). Labels from `CatalogSection.tsx` and `DressEditor.tsx`.

| Key | Verified against | `he` | `ar` | Status |
|---|---|---|---|---|
| `guide.catalog.1` | `CatalogSection.tsx:206` («עריכה»), `:243` («מחיר בתיאום»); `manage-restyle.md`'s `DressEditor` row (name/description/price + price-visibility toggle) | כל שמלה נפתחת בכפתור «עריכה», ובתוכה נמצאים השם, התיאור, המחיר והמתג שקובע אם המחיר מוצג ללקוחה או שמופיע במקומו «מחיר בתיאום». | *(identical)* | DRAFTED |
| `guide.catalog.2` | `VariantMatrix` (size × quantity grid) + `CatalogSection.tsx:15` («אזל מהמלאי»). ⚠ It describes what the **console list** shows and makes no claim about the storefront — the earlier draft asserted a sold-out size stays visible on the public site, which this deck did not verify | טבלת המידות שבתוך השמלה קובעת אילו מידות קיימות וכמה יחידות יש מכל אחת, ושמלה שכל מידותיה אזלו מסומנת ברשימה כ«אזל מהמלאי». | *(identical)* | DRAFTED |
| `guide.catalog.3` | `MediaGallery` (upload + reorder + delete-per-photo) and `CatalogSection.tsx:247` («אין תמונות»). Same restraint: order is editable — which is verifiable — rather than "the first one is the cover", which is not | התמונות מועלות בתוך השמלה ואפשר לשנות את סדרן, ושמלה בלי תמונות מסומנת ברשימה כ«אין תמונות». | *(identical)* | DRAFTED |

### 2.7 `bookings` — «תורים» · ALL · 3 steps

| Key | Verified against | `he` | `ar` | Status |
|---|---|---|---|---|
| `guide.bookings.1` | `booking.dateLabel` («תאריך»), `booking.dayCount`, and the four status words `booking.statusConfirmed/Completed/NoShow/Cancelled` quoted byte-identically | הרשימה מציגה את התורים של תאריך אחד בכל פעם — התאריך נבחר למעלה בשדה «תאריך» — ומצב כל תור («מאושר», «התקיים», «לא הגיעה», «בוטל») מופיע בשורה שלו. | *(identical)* | DRAFTED |
| `guide.bookings.2` | `booking.detailTitle` («פרטי התור»), `booking.customerHeading`, `booking.when`, `booking.dress`, `booking.payment`, `booking.back` («חזרה לרשימה») | לחיצה על שורה פותחת את «פרטי התור» — הלקוחה, המועד, השמלה ומצב התשלום — ו«חזרה לרשימה» מחזירה לאותו תאריך. | *(identical)* | DRAFTED |
| `guide.bookings.3` | ⚠ **The one row in this deck the `/נשלח\|תישלח\|בדרך/` guard is aimed at (rule 2).** Resolved by wording, and the wording is also the true statement: `booking.deliveryNotice` exists because the platform swallows send errors and therefore has **no evidence** a message was delivered. The step says what the console records and then says what it is not | שינוי מועד וביטול נעשים מתוך «פרטי התור», והמסך רושם את מה שהשתנה בבוטיק — הוא אינו עדות למה שהגיע ללקוחה בטלפון שלה. | *(identical)* | DRAFTED |

### 2.8 `customers` — «לקוחות» · ALL · 2 steps

| Key | Verified against | `he` | `ar` | Status |
|---|---|---|---|---|
| `guide.customers.1` | `customers.bookingsHeading` («היסטוריית תורים»), `customers.notesHelp` («ההערות נשמרות בכרטיס ונראות לצוות הבוטיק בלבד»), `customers.tagsHelp` | כרטיס לקוחה מרכז את היסטוריית התורים שלה, הערות פנימיות שנראות לצוות הבוטיק בלבד, ותגיות לסימון. | *(identical)* | DRAFTED |
| `guide.customers.2` | `customers.searchLabel` («חיפוש לפי שם או טלפון»), `customers.messagesHeading` («יומן הודעות»), `customers.messagesHelp` («יומן לקריאה בלבד. אי אפשר לערוך או למחוק רשומה.»). ⚠ Uses the shipped heading «יומן הודעות» and **never** «הודעות שנשלחו», which the register guard forbids and which would be false over `status = 'failed'` rows | החיפוש למעלה עובד לפי שם או לפי מספר טלפון, ו«יומן ההודעות» שבתוך הכרטיס הוא לקריאה בלבד — אי אפשר לערוך או למחוק בו שורה. | *(identical)* | DRAFTED |

### 2.9 `board` — «לוח היום» · ALL · 3 steps

⚠ **Step 3 covers the floor panel that `App.tsx:258-263` renders beneath the board for these two roles only** — and by rule 6 it must not do so by naming «הצוות בקומה», which is a `FLOOR_ONLY` nav row neither reader has.

| Key | Verified against | `he` | `ar` | Status |
|---|---|---|---|---|
| `guide.board.1` | `board.heading`, `board.dayLine` («היום · {{date}}»), `board.now` («עכשיו {{time}}»), `board.emptyBody` (which already routes the reader to «תורים» for another date) | הלוח מציג את תורי היום הנוכחי בלבד, לפי שעה, והשורה «עכשיו» מסמנת בתוכם את הרגע הזה — לתאריך אחר עוברים למסך «תורים». | *(identical)* | DRAFTED |
| `guide.board.2` | `board.checkIn` («הגיעה»), `board.checkedInAt` («נרשמה הגעה · {{time}}»), `board.undo` («ביטול הרישום»); and `board.checkIn`'s own comment, which records that a booking marked `no_show` after a check-in reads as two true facts and not a contradiction | כשלקוחה מגיעה לוחצים «הגיעה» בשורה שלה והפעולה נרשמת עם השעה, ו«ביטול הרישום» מבטל את הרישום הזה בלבד ולא את התור. | *(identical)* | DRAFTED |
| `guide.board.3` | `App.tsx:258-263` (the `FloorPanel` beneath `BoardSection`), `board.updatedAt` («עודכן {{time}}»). ⚠ **rule 6**: names the panel, not the nav row. ⚠ **rule 9**: names the event «עודכן», never a refresh rate | מתחת ללוח מופיע פאנל הקומה — מי מהצוות נמצאת בקומה, מצב חדרי המדידה והממתינות בתור — והשורה «עודכן» למעלה אומרת מתי המידע נקרא לאחרונה. | *(identical)* | DRAFTED |

### 2.10 `floor` — «הצוות בקומה» · FLOOR_ONLY · 3 steps

⚠ **For reception, a sales assistant and (with `atelier`) a seamstress this is the only screen they will ever see**, so these are the three longest sentences in the deck — three panels totalling ~2,900 lines across `FloorPanel` / `RoomsPanel` / `WaitlistPanel` (`design.md` §10 F-8).

| Key | Verified against | `he` | `ar` | Status |
|---|---|---|---|---|
| `guide.floor.1` | `floor.statusAvailable` («פנויה»), `floor.statusOccupied` («תפוסה»), `floor.statusBreak` («בהפסקה»), `floor.breakStart` («להפסקה»), `floor.breakEnd` («חזרה») — and F57's rule that pause/resume is **one button whose name changes** | החלק העליון מראה מי מהצוות נמצאת בקומה ובאיזה מצב — «פנויה», «תפוסה» או «בהפסקה» — ו«להפסקה» ו«חזרה» הם אותו כפתור שמשנה את המצב שלך או של עמיתה. | *(identical)* | DRAFTED |
| `guide.floor.2` | `rooms.heading` («חדרי מדידה»), `rooms.free` («פנוי»), `rooms.occupied` («תפוס»), `rooms.release` («שחרור»), `rooms.handover` («העברה לעמיתה»). ⚠ The masculine «פנוי / תפוס» here and the feminine «פנויה / תפוסה» above are **deliberately different words** for different subjects (`rooms.free`'s own comment) and the step keeps them apart | בחלק «חדרי מדידה» כל חדר הוא «פנוי» או «תפוס» — «שחרור» מפנה חדר בסיום המדידה, ו«העברה לעמיתה» משאיר את הלקוחה בחדר ומעביר את האחריות עליו. | *(identical)* | DRAFTED |
| `guide.floor.3` | `waitlist.heading` («ממתינות בתור»), `waitlist.call` («קראי»), `waitlist.assign` («שבצי לחדר»), and `waitlist.noFreeRoom`'s comment — *"the only surface that explains why «שבצי לחדר» vanished from every row … at one moment"*. The step teaches the disappearance in advance, which is the single most confusing thing on this panel | ב«ממתינות בתור» מופיעות מי שנרשמו בכניסה מהטלפון, לפי סדר הגעה — «קראי» מסמן שקראת לה בשמה, «שבצי לחדר» מכניס אותה לחדר, וכשאין חדר פנוי הכפתור נעלם עד שיתפנה אחד. | *(identical)* | DRAFTED |

### 2.11 `atelier` — «תפירה» · ATELIER_ROLES · 3 steps

⚠ **`AtelierSection.tsx:1344-1356`** — a seamstress may work her own ticket or an unassigned one; **on a colleague's she sees the facts and no controls at all**. Rule 5, and step 3 makes the rule itself the content.

| Key | Verified against | `he` | `ar` | Status |
|---|---|---|---|---|
| `guide.atelier.1` | `atelier.stage.intake/inProgress/qc/ready/delivered` («התקבל», «בעבודה», «בקרה», «מוכן», «נמסר») — all five quoted byte-identically, and «נמסר» deliberately never «נשלח», which the register guard rejects outright | לוח התפירה בנוי מחמישה שלבים — «התקבל», «בעבודה», «בקרה», «מוכן» ו«נמסר» — וכרטיס עובר ביניהם לפי הסדר הזה. | *(identical)* | DRAFTED |
| `guide.atelier.2` | `atelier.dueDate` («יעד {{date}}»), `atelier.effortMinutes`, `atelier.assignLabel` («תופרת»). ⚠ **Rule 5**: it lists what a card **holds**, and says nothing about who may change it — that is step 3's job and step 3 is honest about it | כרטיס נפתח בלחיצה ומרכז את הלקוחה, השמלה, תאריך היעד, משך העבודה המשוער והתופרת המשויכת אליו. | *(identical)* | DRAFTED |
| `guide.atelier.3` | ⚠ **Rule 5, stated as the content.** `AtelierSection.tsx:1344-1356`'s `mayWork` / `mayEdit`, and its comment: *"not a disabled button, not a lock glyph, not an «אין לך הרשאה» line"*. The guide is the one surface where the model can be explained **once**, instead of on a screen she opens fifty times a shift | הכפתורים שמופיעים על כרטיס תלויים בתפקיד ובשיוך — תופרת עובדת על הכרטיסים שלה ועל כרטיסים שעדיין לא שויכו, ועל כרטיס של עמיתה היא רואה את הפרטים בלבד. | *(identical)* | DRAFTED |

### 2.12 `checkinQr` — «קוד סריקה» · ALL · 2 steps

| Key | Verified against | `he` | `ar` | Status |
|---|---|---|---|---|
| `guide.checkinQr.1` | `checkinQr.intro`, `checkinQr.posterLine`, `checkinQr.urlLabel` («כתובת הרישום:») and `checkinQr.urlHint` («אפשר גם להקליד את הכתובת בדפדפן») — which exists because *a camera that will not focus is the ordinary failure of a printed code* | הדף הזה הוא השלט לכניסה — מי שסורקת את הקוד מהטלפון שלה מגיעה ישירות לטופס הרישום לתור, והכתובת מודפסת גם באותיות למי שהמצלמה שלה לא מצליחה לסרוק. | *(identical)* | DRAFTED |
| `guide.checkinQr.2` | `checkinQr.printCta` («הדפסה»). ⚠ It says **the address stays the same address** rather than "the code never changes" — the first is what the poster shows and this deck can see; the second is a claim about a token's lifetime it cannot | «הדפסה» מדפיסה את הדף הזה כפי שהוא, והכתובת נשארת אותה כתובת — אפשר להדפיס שלט חדש בכל פעם שהקודם נקרע או דוהה. | *(identical)* | DRAFTED |

### 2.13 `staff` — «צוות» · owner-only · 2 steps

| Key | Verified against | `he` | `ar` | Status |
|---|---|---|---|---|
| `guide.staff.1` | `staff.createHeading` («הוספת אשת צוות»), `staff.displayNameLabel`, `staff.emailLabel`, `staff.roleLabel`, `staff.passwordLabel`, and `staff.passwordNotice` («יש למסור את הסיסמה לעובדת בעצמך. המערכת אינה מעבירה אותה לאיש.») — **whose wording this step reuses rather than respelling**, because a second spelling of one fact in one console is a defect | הוספת אשת צוות דורשת שם, אימייל, תפקיד וסיסמה — התפקיד הוא שקובע לאילו מסכים היא נכנסת, ואת הסיסמה יש למסור לה בעצמך משום שהמערכת אינה מעבירה אותה לאיש. | *(identical)* | DRAFTED |
| `guide.staff.2` | `staff.deactivateCta` («השבתה») and its comment — *"«השבתה», never «מחיקה»: the row is soft-deleted and its audit trail lives"* — plus `staff.deactivateBody` («…אפשר להוסיף אותה מחדש בכל עת») | «השבתה» עוצרת את הגישה של אשת הצוות לניהול הבוטיק ואינה מוחקת אותה — ההיסטוריה שלה נשמרת ואפשר להחזיר אותה בכל עת. | *(identical)* | DRAFTED |

### 2.14 `gateway` — «סליקה ותשלומים» · owner-only · 2 steps

| Key | Verified against | `he` | `ar` | Status |
|---|---|---|---|---|
| `guide.gateway.1` | `gateway.heading` («חיבור לסליקה») and `gateway.writeOnlyNotice` («מטעמי אבטחה הפרטים אינם ניתנים לצפייה לאחר השמירה. שמירה מחליפה את כל הפרטים.»), whose two facts this step compresses into one clause without respelling either | המסך הזה מחבר את הבוטיק לחשבון הסליקה שדרכו נגבות המקדמות, ומטעמי אבטחה הפרטים אינם ניתנים לצפייה אחרי השמירה — שמירה נוספת מחליפה אותם במלואם. | *(identical)* | DRAFTED |
| `guide.gateway.2` | `gateway.notConnected` («עדיין לא חובר חשבון סליקה»), `gateway.depositsWithoutGateway`, and the 2026-07-31 ruling *"Q1 no-gateway → hide the deposit and book anyway"*, which `booking.paymentActionNoDeposit` is the shipped evidence of | כל עוד אין חשבון מחובר, תור נקבע גם בלי מקדמה — המתג בהגדרות נשאר כפי שהוא, והמקדמה פשוט אינה נגבית עד שהחיבור יושלם. | *(identical)* | DRAFTED |

---

## 3. The storefront — 2 keys, under the existing `checkin` section

⚠ **Not a new top-level `guide` section** (DL21). Both strings render on `/checkin` and nowhere else, and `checkin` (`he.ts:408`) is already in `i18n-keys.test.ts`'s `SECTIONS` — so the dotted-literal source scan (`:21`, `:39`) covers them with **no edit to the scanner**.

⚠ **Rule 3 governs both rows.** The hint is about **the queue** — what checking in puts her into, what she gets back, and that a staffer calls her. It states no data-handling fact of any kind. `checkin.notice` remains the only such text on the page and is untouched.

| Key | What it must say | `he` | `ar` | Status |
|---|---|---|---|---|
| `checkin.guideTrigger` | The disclosure's label, and it must be the **reader's question**, not the product's heading — she is standing in a doorway with a phone, deciding whether to fill in a form for strangers. A question mark is permitted (only `!` is banned). ⚠ **Deliberately NOT «מה קורה עם הפרטים שלי?»**, which would be a second, unapproved collection notice beside a legally-mandated always-visible one (DL15) | מה קורה אחרי הרישום? | מה קורה אחרי הרישום? | DRAFTED |
| `checkin.guideHint` | Three facts and no fourth: it puts her in the boutique's waiting line, a page opens with her place in it that she can keep open, and a member of staff calls her by name. ⚠ Register-checked against `/נשלח\|תישלח\|בדרך/` — and it avoids «שליחה» entirely, which the submit button already owns, so nothing here can read as a message going anywhere. ⚠ It does **not** mention the public queue board: that is `checkin.notice`'s counsel-gated clause and repeating it here would be the second notice rule 3 forbids | הרישום מכניס אותך לתור ההמתנה של הבוטיק — בסיום נפתח עמוד עם מקומך בתור שאפשר להשאיר פתוח בטלפון, ואשת צוות תקרא לך בשם כשיגיע תורך. | *(identical)* | DRAFTED |

⚠ **The storefront's new `ar` guard is a VALUE-parity check** (`ar.checkin.guideTrigger === he.checkin.guideTrigger`, same for `guideHint`) and must be written as such. The F19 block beside it (`i18n-keys.test.ts:145-155`) is a **presence** check (`typeof resolve(key, ar.translation) === "string"`), and **the storefront has never had a value-parity guard anywhere.** This is the first, deliberately scoped to these two keys; widening it is a different feature's decision.

---

## 4. The scan

| Check | Result |
|---|---|
| **Console keys** | 7 chrome + 36 steps = **43**. Matches D8 and `HE_F60`'s `>= 43` floor exactly |
| **Steps per section** | 2 + 3 + 3 + 3 + 2 + 3 + 3 + 2 + 3 + 3 + 3 + 2 + 2 + 2 = **36**, matching D1 row for row |
| **Sections covered** | **14 / 14**, derived from `App.tsx:24-41` on 2026-08-04 — not from any document |
| **Storefront keys** | **2**, both under the existing `checkin` section |
| `"!"` | **0 occurrences** across all 45 values |
| `/נשלח\|תישלח\|בדרך/` | **0 matches.** The two nearest strings are `guide.bookings.3` (says «הגיע ללקוחה», and says the console is not evidence of it) and `guide.atelier.1` (quotes the shipped «נמסר», which exists precisely because «נשלח» is banned) |
| Digits | **only** in `guide.progress`, both interpolated, both between Hebrew words (rule 10) |
| Interpolation | `{{section}}` (chrome), `{{step}}` + `{{total}}` (chrome). **Zero interpolation in all 36 steps** — nothing to isolate, nothing to agree with, no `<bdi>` anywhere in this namespace |
| `…` as placeholder | **0**. Every value is a real string (rule 12) |
| Sections whose labels were read from the component, not `he.ts` | **4** — `hours`, `types`, `terms`, `catalog` (rule 4) |
| Rows carrying an intra-section role ⚠ | **2** — `guide.terms.2`, `guide.atelier.3` (rule 5) |
| Rows that avoid naming an unreachable section ⚠ | **2** — `guide.profile.3`, `guide.board.3` (rule 6) |

---

## 5. Nothing is reused, and that is a decision

Every other feature in this console reuses shipped strings and this deck reuses **none**. The reason is that the two kinds of string are not interchangeable: a shipped label is a **name on a control** («הגיעה», «שחרור», «השבתה») and a step is a **sentence about it**. Reusing `board.checkIn` as a step would put the word «הגיעה» alone in a dialog with no control under it.

**What the steps do instead is quote.** Wherever a step names a control it uses the shipped label **byte-identically, inside guillemets** — «הגיעה», «ביטול הרישום», «שבצי לחדר», «העברה לעמיתה», «השבתה», «העברה לארכיון», «אזל מהמלאי», «מחיר בתיאום», «הדפסה», «קיבולת», «נדרשת מקדמה», «מקדמה (₪)», «סדר תצוגה», «סגור כל היום», «עודכן», «עכשיו», «התקבל», «בעבודה», «בקרה», «מוכן», «נמסר», «פנוי», «תפוס», «פנויה», «תפוסה», «בהפסקה», «להפסקה», «חזרה», «קראי». **A quoted label that drifts from its control is the failure mode of this whole deck** (spec R1), and quoting rather than paraphrasing is what makes the drift greppable.

⚠ **Two shipped strings this deck deliberately does NOT quote**: `guide.customers.2` writes «יומן ההודעות» (definite) where the heading is «יומן הודעות» (indefinite), because a heading names a thing and a sentence refers back to one; and `guide.floor.2` writes «חדרי מדידה» matching `rooms.heading` exactly. Both are noted so a reviewer diffing against `he.ts` sees the one intentional inflection.

---

## 6. Corrections and divergences recorded

**C-1 ⚠ CORRECTS spec D5's counter.** D5 illustrates «שלב 2 מתוך 4»; **every one of the fourteen sections has 2 or 3 steps**, so «מתוך 4» is unrepresentable. And D5's stated constraint — *"Both digits must sit between Hebrew words … neither at a string edge"* — is **unsatisfiable** for a two-number Hebrew counter without a trailing word: «שלב {{step}} מתוך {{total}}» leaves `{{total}}` at the edge. Resolved in copy: **«שלב {{step}} מתוך {{total}} במדריך»**, whose extra word also names the speaking region for the AT (§1). `isolateLtr` is not the alternative and would be actively wrong — see §1.

**C-2 ⚠ The console ships two words for one thing, and this deck picks one.** «מקדמה» is used by `profile.depositsEnabled`, `gateway.depositsWithoutGateway` and `TypesSection.tsx:106`; «פיקדון» is used by `booking.paymentActionNoDeposit` and `booking.refundDue`'s neighbours. **This deck uses «מקדמה» throughout** — it is the word on the two switches an owner actually touches, and it is the word in the section headings. **F60 does not repair the split**: it edits neither block, and a drive-by i18n rename inside the payments copy is exactly the unrelated diff this program's review sends back. Recorded for whoever next opens `booking.*`.

**C-3 The guide's steps are the only place in the product where the atelier's permission model is written down.** `AtelierSection.tsx:1344-1356` deliberately renders **no** explanation — no disabled button, no lock glyph, no «אין לך הרשאה» line — on the grounds that an explanation on a screen she opens fifty times a shift is noise. `guide.atelier.3` is the surface where that argument's other half lands: the model is explained **once**, in a walkthrough she opens deliberately. That is the strongest single justification this feature has, and it is worth stating because F60 otherwise ships no capability.
