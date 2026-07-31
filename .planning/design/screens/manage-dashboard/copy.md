# Copy deck — F52 KPI dashboard (`apps/manage`, section «סקירה»)

**Date**: 2026-07-31 · **Status**: DRAFTED under the approved register, self-approved with the design gate (Interview **Q2** — assembled from three shipped `packages/ui` components, no novel pattern) · **Owner of the Hebrew: the user** · **Consumes**: `.planning/specs/kpi-dashboard.md` (D1–D11) · **Lands in**: `Frontend/apps/manage/src/i18n/he.ts` (`nav.dashboard` + a new flat `dashboard.*` block) and `Frontend/apps/manage/src/i18n/ar.ts`

**F52 adds no SMS template, no email and no toast.** There is no §SMS section in this deck. The section is read-only: it has no mutation, so it has no success message, no confirmation, no validation message and no destructive-action copy. Every string below is a label, a heading, a help line or one of the four state sentences.

## 0. The rules this deck is written under — hard constraints, not preferences

1. **Zero exclamation marks** (pre-decided #5). Mechanically enforced in `__tests__/i18n.test.ts`.
2. **No string may contain «נשלח», «תישלח» or «בדרך».** The guard exists for SMS claims and F52 sends nothing, but «בדרך» is a natural Hebrew word for a rising trend and would red-fail a test whose message is about sends. The deck is written around it rather than discovering it — that is why §5 says «נספרים תורים…» and no string anywhere describes a direction of travel.
3. **Zero, unknown and too-small-to-show are three different facts and get three different strings.** `0.0%` is rendered arithmetic (no key). `dashboard.notEnoughData` is a `null` rate. `dashboard.rateUnderFloor` is a non-zero rate the one-decimal precision cannot display. A screen that collapsed any two of them would tell a pilot boutique that it had no cancellations when it had one.
4. **The weekly count is appointments the boutique HELD — seat-slots not cancelled — never appointments that took place** (spec D5). The bar includes `no_show` rows by an asserted server invariant and sits on the same screen as a no-show rate, so a Hebrew label promising attendance would contradict the tile beside it in the pilot's first week. `dashboard.bookingsColumn` and `dashboard.weeksHelp` carry this together: the column names the predicate, the help line says out loud that no-shows are inside it.
5. **The no-show denominator is stated in words**, not implied by a percentage sign (spec D5, Risk 5). `dashboard.noShowHelp` names it and `dashboard.unclassifiedLabel` ships the count it excludes.
6. **No sentence bridges the two ranges** (Risk 13). History ends last Saturday, the forward panel starts today, and 0–6 days sit on neither. The two range labels are deliberately **different words** — «התקופה:» for history, «הטווח:» for forward — so the two spans cannot read as one.
7. **The copy names no server constant except one.** `HISTORY_WEEKS`, `TOP_APPOINTMENT_TYPES` and the week count are never spelled out — the client renders whatever array arrives and mirrors no bound (spec: no `MIRRORS` row). The single exception is «שבעת הימים» in `dashboard.forwardHeading`, which the spec requires; the real dates render immediately beneath it in `dashboard.forwardRange`, so if `FORWARD_WINDOW_DAYS` ever changes the two disagree visibly instead of silently.
8. **Every value is a real string.** No `…`-as-placeholder, nothing to be filled in later.
9. **The `ar` column is the approved Hebrew, standing in untranslated** (Interview Q3 / pre-decided #47), **never an empty string** — i18next's `returnEmptyString` default renders `""` rather than falling back.

**43 rows.** F52 invents every one of them and reuses no existing key. `i18n.test.ts`'s F52 floor is `toBeGreaterThan(40)`.

There are no client-side validation messages in this deck (nothing is entered) and no error-code→Hebrew map (§2 records why one string covers every `ApiError`).

---

## 1. Navigation and section chrome

| Key | What it must say | Approved Hebrew (`he`) | `ar` (untranslated) | Status |
|---|---|---|---|---|
| `nav.dashboard` | The **first** console nav item, rendered for **both** roles (spec D10). «סקירה» over «לוח מחוונים» — a boutique owner reads an overview, not a dashboard | סקירה | סקירה | DRAFTED |
| `dashboard.heading` | The section `h2` under `ConsoleShell`'s `sr-only` `h1`. Identical to the nav word, the `staff.heading` precedent | סקירה | סקירה | DRAFTED |
| `dashboard.generatedOnLabel` | Label before the server's `generated_on` date. The console renders no "as of" it computed itself (spec D8), so this labels a value that came off the wire | נכון לתאריך: | נכון לתאריך: | DRAFTED |

## 2. Section states

One error string. **Not** because either code is unreachable — `apiFetch` has no 401 interceptor and `NOT_AUTHORIZED` became reachable the moment the dashboard became the landing section (spec D10) — but because the section renders the same sentence for **any** `ApiError`, the `BookingsSection` shape. That also keeps `errorMessage()`'s verbatim **English** server text off the console's landing screen.

| Key | What it must say | Approved Hebrew (`he`) | `ar` | Status |
|---|---|---|---|---|
| `dashboard.loading` | The `role="status"` region while the one fetch is in flight. The shipped console announces nothing while loading; this section reuses the region the total needs anyway | טוענים את הנתונים. | טוענים את הנתונים. | DRAFTED |
| `dashboard.summary` | The announced total, interpolated and passed through `isolateLtr`. The Hebrew around the placeholder carries **no other digits**, which is that helper's stated precondition. States the predicate again so the announced number cannot be heard as attendance (§0 rule 4) | סך התורים שלא בוטלו בתקופה: {{count}} | סך התורים שלא בוטלו בתקופה: {{count}} | DRAFTED |
| `dashboard.loadFailed` | The load failed — the **outage** register: recoverable, unblaming, no technical words, no retry control (reopening the section refetches). Deliberately the same register and shape as `staff.loadFailed` | לא הצלחנו לטעון את הנתונים כרגע. | לא הצלחנו לטעון את הנתונים כרגע. | DRAFTED |
| `dashboard.firstRunNote` | Day one. Shown only while there is **no booking anywhere on the screen** — every `status_totals` at zero AND `forward.booked` at zero (amended in review; "the whole history is zero" was read as "every week bar is zero", and `weeks[]` excludes cancellations and the current in-progress week, so the unscoped «כאן» would sit above a card reading 12 or 100.0%) — as one muted line under the heading — **never an `EmptyState`**, which would hide the forward panel (spec D10, Risk 1). It explains that the screen fills itself, states the fact that the numbers are zero, and promises nothing about when | המסך הזה מתמלא מעצמו ככל שנקבעים תורים. עד אז המספרים כאן הם אפס. | המסך הזה מתמלא מעצמו ככל שנקבעים תורים. עד אז המספרים כאן הם אפס. | DRAFTED |

## 3. The two shared value strings

| Key | What it must say | Approved Hebrew (`he`) | `ar` | Status |
|---|---|---|---|---|
| `dashboard.notEnoughData` | A rate that is `null` — **not computable**, never `0.0%`. Used by all four nullable values (`cancellation_rate`, `no_show_rate`, `repeat_rate`, and `utilization` via §4's own sentence). «עדיין» is load-bearing: it says the number is missing, not impossible | אין עדיין מספיק נתונים לחישוב. | אין עדיין מספיק נתונים לחישוב. | DRAFTED |
| `dashboard.rateUnderFloor` | A non-zero rate that rounds to `0.0%` at one decimal. **Spelled in words, not as `<0.1%`** — a bare `<` inside an RTL paragraph reads as a bracket and mirrors, and this string sits unisolated in Hebrew running text. A deliberate, recorded departure from the spec's shorthand for the same fact | פחות מ־0.1% | פחות מ־0.1% | DRAFTED |

## 4. The forward panel

The **first** panel on the screen: it is the only one with a real number on a boutique's first day, and it is the panel a shift manager opens the console for.

| Key | What it must say | Approved Hebrew (`he`) | `ar` | Status |
|---|---|---|---|---|
| `dashboard.forwardHeading` | The panel `h3`. «תפוסה» and not «עומס» — occupancy is a fact, load is a judgement. The one string in the deck that names a server constant (§0 rule 7) | תפוסה בשבעת הימים הקרובים | תפוסה בשבעת הימים הקרובים | DRAFTED |
| `dashboard.forwardRange` | Label before `<bdi dir="ltr">{from_date}–{to_date}</bdi>`. «הטווח» — deliberately a different word from §5's «התקופה», so the two spans cannot read as one (§0 rule 6) | הטווח: | הטווח: | DRAFTED |
| `dashboard.forwardValueLabel` | The `<dt>` for `utilization` | אחוז התפוסה | אחוז התפוסה | DRAFTED |
| `dashboard.forwardCapacityLabel` | The `<dt>` for `capacity`. «מקומות» — a seat-slot, which is what capacity means here; never «שעות», because the grid has no duration (spec Risk 7) | סך המקומות בטווח | סך המקומות בטווח | DRAFTED |
| `dashboard.forwardBookedLabel` | The `<dt>` for `booked` | מקומות שנתפסו | מקומות שנתפסו | DRAFTED |
| `dashboard.forwardHelp` | **Closes Risk 6 in copy.** The number moves through the day with no booking changing, because the engine drops every start time that has passed. This says so plainly, and it is why the heading says «הקרובים» and not «בשבוע הבא» — a fixed window is exactly what this is not | הספירה כוללת רק מועדים שאפשר עדיין להציע מהרגע הזה. מועדים שכבר חלפו היום אינם נכללים בה. | הספירה כוללת רק מועדים שאפשר עדיין להציע מהרגע הזה. מועדים שכבר חלפו היום אינם נכללים בה. | DRAFTED |
| `dashboard.forwardNoHours` | `capacity == 0`. Names **closed hours**, not zero demand — the distinction is the whole point, because the remedy is a different console section and the sentence has to point at it. Replaces the whole panel body; no bar is drawn for a value that does not exist | אין שעות פעילות פתוחות בטווח הזה, ולכן אין כאן מה לחשב. | אין שעות פעילות פתוחות בטווח הזה, ולכן אין כאן מה לחשב. | DRAFTED |

## 5. The weekly table

| Key | What it must say | Approved Hebrew (`he`) | `ar` | Status |
|---|---|---|---|---|
| `dashboard.weeksHeading` | The panel `h3`. Names no week count (§0 rule 7) | תורים לפי שבוע | תורים לפי שבוע | DRAFTED |
| `dashboard.weeksRange` | Label before `<bdi dir="ltr">{from_date}–{to_date}</bdi>` | התקופה: | התקופה: | DRAFTED |
| `dashboard.weeksHelp` | **The §0 rule 4 line.** States the predicate and then says out loud that no-shows are counted in it. Without the second half, the bar and the no-show tile on the same screen contradict each other and the owner has to guess which one lied | נספרים תורים שנקבעו ולא בוטלו, כולל תורים שהלקוחה לא הגיעה אליהם. | נספרים תורים שנקבעו ולא בוטלו, כולל תורים שהלקוחה לא הגיעה אליהם. | DRAFTED |
| `dashboard.weeksTableCaption` | `<caption class="sr-only">`. The table's accessible name, so an AT announces what it is before its first cell | תורים שלא בוטלו, לפי שבוע | תורים שלא בוטלו, לפי שבוע | DRAFTED |
| `dashboard.weekColumn` | `<th scope="col">` over the date column. The cell shows a **start** date, and the header has to say so or a reader takes it for the whole week's label | תחילת שבוע | תחילת שבוע | DRAFTED |
| `dashboard.bookingsColumn` | `<th scope="col">` over the count column, **and reused for the appointment-types table** — the two counts must state the same predicate or the screen carries two meanings of one word. See the open item in `manage-dashboard.md`: this requires the service to fold types under the non-cancelled predicate too | תורים שלא בוטלו | תורים שלא בוטלו | DRAFTED |

## 6. Cancellations and no-shows

The two counts in this section are rendered as **independent labelled values, never as a partition** — a row cancelled before migration 0010 carries a NULL attribution and is in neither (Risk 11), so no string here may imply they sum to the cancellation count. That is why they are two `<dt>`s and not one «X מתוך Y» sentence.

| Key | What it must say | Approved Hebrew (`he`) | `ar` | Status |
|---|---|---|---|---|
| `dashboard.ratesHeading` | The panel `h3` | ביטולים ואי־הגעה | ביטולים ואי־הגעה | DRAFTED |
| `dashboard.cancellationRateLabel` | The `<dt>` for `cancellation_rate` | שיעור הביטולים | שיעור הביטולים | DRAFTED |
| `dashboard.cancellationHelp` | The denominator in words. «בכל סטטוס» is the exact fact — this rate is over all four statuses, unlike the one below it | מתוך כל התורים שנקבעו בתקופה, בכל סטטוס. | מתוך כל התורים שנקבעו בתקופה, בכל סטטוס. | DRAFTED |
| `dashboard.cancelledByCustomerLabel` | The `<dt>` for `cancelled_by_customer` | ביטולים ביוזמת הלקוחה | ביטולים ביוזמת הלקוחה | DRAFTED |
| `dashboard.cancelledByOwnerLabel` | The `<dt>` for `cancelled_by_owner`. Without this pair a boutique that closed for a week and cancelled twenty appointments itself reads its own closure as customer flakiness | ביטולים ביוזמת הבוטיק | ביטולים ביוזמת הבוטיק | DRAFTED |
| `dashboard.noShowRateLabel` | The `<dt>` for `no_show_rate` | שיעור אי־ההגעה | שיעור אי־ההגעה | DRAFTED |
| `dashboard.noShowHelp` | **The sharp denominator, stated in words** (§0 rule 5). «בלבד» is the whole sentence's job: it tells the owner the rate is not over all her appointments, which is what makes the number beside it readable at small denominators | מתוך התורים שסומנו כהתקיימו או כאי־הגעה בלבד. | מתוך התורים שסומנו כהתקיימו או כאי־הגעה בלבד. | DRAFTED |
| `dashboard.unclassifiedLabel` | The `<dt>` for `status_totals.confirmed` — appointments in a past window that the owner never marked | תורים שעברו ולא סומנו | תורים שעברו ולא סומנו | DRAFTED |
| `dashboard.unclassifiedHelp` | **The Risk 5 bound, made visible.** Says what the number is and that it is outside the rate above. An owner who marks three no-shows and nothing else reads 100% — this line is what tells her the denominator was three | תורים שכבר עברו ולא סומנו כהתקיימו או כאי־הגעה. הם אינם נכללים בשיעור אי־ההגעה. | תורים שכבר עברו ולא סומנו כהתקיימו או כאי־הגעה. הם אינם נכללים בשיעור אי־ההגעה. | DRAFTED |

## 7. Customers

| Key | What it must say | Approved Hebrew (`he`) | `ar` | Status |
|---|---|---|---|---|
| `dashboard.customersHeading` | The panel `h3` | לקוחות בתקופה | לקוחות בתקופה | DRAFTED |
| `dashboard.customersHelp` | The cohort definition (spec D6): distinct customers on **non-cancelled** bookings in the window. A bride who booked and cancelled did not visit, and the copy has to say the predicate or «סך הלקוחות» reads as everyone in the address book | נספרות לקוחות עם תור אחד לפחות בתקופה שלא בוטל. | נספרות לקוחות עם תור אחד לפחות בתקופה שלא בוטל. | DRAFTED |
| `dashboard.customersTotalLabel` | The `<dt>` for `customers.total` | סך הלקוחות | סך הלקוחות | DRAFTED |
| `dashboard.customersNewLabel` | The `<dt>` for `customers.new` | לקוחות חדשות | לקוחות חדשות | DRAFTED |
| `dashboard.customersReturningLabel` | The `<dt>` for `customers.returning` | לקוחות חוזרות | לקוחות חוזרות | DRAFTED |
| `dashboard.repeatRateLabel` | The `<dt>` for `customers.repeat_rate` | שיעור החזרה | שיעור החזרה | DRAFTED |
| `dashboard.repeatRateHelp` | Why this is not the same number as «לקוחות חוזרות». «אי פעם» is the lifetime scope the spec defines, and it is what makes a bride who booked twice inside the window both **new** and part of this rate | חלקן של הלקוחות בתקופה שקבעו בבוטיק יותר מתור אחד אי פעם. | חלקן של הלקוחות בתקופה שקבעו בבוטיק יותר מתור אחד אי פעם. | DRAFTED |

## 8. Appointment types

| Key | What it must say | Approved Hebrew (`he`) | `ar` | Status |
|---|---|---|---|---|
| `dashboard.typesHeading` | The panel `h3` | סוגי התורים המבוקשים | סוגי התורים המבוקשים | DRAFTED |
| `dashboard.typesHelp` | **Honest at any list length** (Risk 14). Says the list is the most-booked types and never claims completeness, so a boutique with more than five types is not told something false — and it names no number, so it does not mirror `TOP_APPOINTMENT_TYPES` | מוצגים סוגי התורים שנקבעו הכי הרבה פעמים בתקופה. | מוצגים סוגי התורים שנקבעו הכי הרבה פעמים בתקופה. | DRAFTED |
| `dashboard.typesTableCaption` | `<caption class="sr-only">` | סוגי תורים לפי מספר התורים בתקופה | סוגי תורים לפי מספר התורים בתקופה | DRAFTED |
| `dashboard.typeColumn` | `<th scope="col">` over the name column. The count column reuses `dashboard.bookingsColumn` (§5) | סוג תור | סוג תור | DRAFTED |
| `dashboard.typesEmpty` | The empty list — one muted line inside the Card, replacing the table. Not an `EmptyState`, not a Card full of nothing. States the fact and stops; the day-one explanation is `dashboard.firstRunNote`'s job and it is already on screen | לא נקבעו תורים בתקופה הזו. | לא נקבעו תורים בתקופה הזו. | DRAFTED |
