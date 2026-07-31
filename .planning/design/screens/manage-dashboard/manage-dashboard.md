# Screen design — F52 KPI dashboard (`apps/manage`, section «סקירה»)

**Date**: 2026-07-31 · **Status**: DRAFTED, design gate self-approved under Interview **Q2** · **Spec**: `.planning/specs/kpi-dashboard.md` (D1–D11) · **Copy**: `./copy.md` · **Tokens**: `.planning/design/system/tokens.md` — binding

## What this screen is

The eighth console section and the one the console **lands on**, for **both roles**. It is the first read-only overview in the product: every other section answers a question about one row, this one answers six questions about a window and refuses a seventh. It has **no interactive control of any kind** — no picker, no filter, no retry, no link, no row that opens anything. That is not an omission, it is the shape: the endpoint takes no parameters (spec D2), so there is nothing on this screen for a user to change.

Two spans, never one. History is the last complete Israeli weeks, ending last Saturday; the forward panel is the next seven days from now. **Nothing on this screen bridges them** — Risk 13's 0–6 uncovered days are real, and a sentence implying continuity would be a lie the design tells on the owner's behalf. Each panel carries its own range line, in its own words.

## Components — all shipped, nothing new, nothing promoted

`SectionHeading` · `Card` · `Skeleton` — three, all exported from `packages/ui/src/index.ts` today. That is the whole component set, and it is the Q2 self-approval argument: **no new `packages/ui` component and no promotion**.

`EmptyState` is deliberately **not** mounted (spec D10: it would hide the forward panel, the one number a day-one boutique can act on). `Badge` is deliberately **not** mounted — no tile places one, and a gold variant would be exactly the promotion Q2 forbids. Both are named here only so the component argument enumerates what actually renders rather than padding itself.

`SectionHeading as="h2"` is the shipped console spelling (`ProfileSection.tsx:103, 148`). Panel headings are plain `<h3 className="text-sm font-semibold text-ink">` — markup, not a component — the idiom `StaffSection.tsx:345`, `TypesSection.tsx:214` and `HoursSection.tsx:162` all use.

## The one hand-built thing: the bar

A track `<span aria-hidden="true" className="block h-2 rounded-sm bg-border">` containing a fill `<span className="block h-2 rounded-sm bg-gold-strong" style={{ inlineSize: \`${pct}%\` }} />`.

- **`inlineSize`, never `width`** — a logical property, so in RTL the fill grows from the inline-start (right) edge. This is the whole reason the spec names the property (D10).
- **`aria-hidden` on the whole bar, always.** It is never `role="progressbar"`: that role announces a task's completion, not a ratio of a static quantity, and an AT would read the utilization bar as an in-flight operation. The repo contains zero `role="progressbar"`, `role="meter"`, `<meter>` or `<progress>` (verified — the only hits are TypeScript's `lib.dom.d.ts`), and F52 adds none. `SetupProgress`'s `aria-hidden` ✓/○ beside a word is the shipped precedent.
- **Remove every bar and the screen loses nothing.** Every value it draws is present as text in the same row. That is the test the builder writes and the rule the design is answerable to.
- **Two different bar semantics on one screen, kept apart by what they sit beside.** The forward bar is **absolute** — its maximum is `forward.capacity`, and it sits beside a **percentage**. The weeks and types bars are **relative** — their maximum is the largest value in the visible list, and they sit beside a **count**. A bar next to a `%` reads as a proportion of a whole; a bar next to a count reads as a comparison with its neighbours. No axis, no gridline and no tick claims otherwise, because there is none.
- Contrast, computed against `tokens.md` and not eyeballed: fill `#9E7B36` on the card surface `#F6F0E6` is **3.47:1** (≥3:1 ✓ — the bar is perceivable as a mark). Fill on the track `#E4DACA` is **2.84:1**, below the non-text floor, and it is exempt for the reason above: the bar is `aria-hidden` decoration entirely redundant to adjacent text. `--color-gold-strong`'s stated job in `tokens.md` is "meaningful non-text UI", which is exactly this; it carries **no text anywhere in this section**.
- No transition on the fill. It renders at its final size, so `prefers-reduced-motion` has nothing to reduce here; `Skeleton`'s pulse is already frozen by `theme.css`.

## Structure — `components/DashboardSection.tsx`, no props

The section takes **no props** and makes its own fetch, `BookingsSection.tsx:27-51` verbatim in shape: `useEffect`, `let cancelled = false`, one `api.getDashboard()`, no interval, no refetch control (D11).

```
SectionHeading as="h2" ornament        dashboard.heading
<p>                                    dashboard.generatedOnLabel  <bdi dir="ltr">{generated_on}</bdi>
<p role="status">                      loading -> dashboard.loading
                                       outage  -> ""
                                       else    -> isolateLtr(dashboard.summary, total)
<p role="alert">                       dashboard.loadFailed                        [outage only]
<Skeleton variant="text" lines={6} />                                              [loading only]
<p>                                    dashboard.firstRunNote     [loaded && the whole history is zero]

Card   forward
  <h3>   dashboard.forwardHeading
  <p>    dashboard.forwardRange  <bdi dir="ltr">{from_date}–{to_date}</bdi>
  capacity > 0
    <dl>  dashboard.forwardValueLabel     -> <bdi dir="ltr">44.0%</bdi>  + bar(utilization)
          dashboard.forwardCapacityLabel  -> <bdi dir="ltr">84</bdi>
          dashboard.forwardBookedLabel    -> <bdi dir="ltr">37</bdi>
    <p>   dashboard.forwardHelp
  else
    <p>   dashboard.forwardNoHours

Card   weeks
  <h3>   dashboard.weeksHeading
  <p>    dashboard.weeksRange   <bdi dir="ltr">{from_date}–{to_date}</bdi>
  <p>    dashboard.weeksHelp
  <table>
    <caption class="sr-only">   dashboard.weeksTableCaption
    <th scope="col">            dashboard.weekColumn · dashboard.bookingsColumn
    one <tr> per week, ascending:
      <th scope="row"><bdi dir="ltr">{d.m}</bdi>
      <td> bar(count / max) + <bdi dir="ltr">{count}</bdi>

Card   rates
  <h3>   dashboard.ratesHeading
  <dl>   dashboard.cancellationRateLabel     -> rate | dashboard.notEnoughData   + dashboard.cancellationHelp
         dashboard.cancelledByCustomerLabel  -> <bdi dir="ltr">{n}</bdi>
         dashboard.cancelledByOwnerLabel     -> <bdi dir="ltr">{n}</bdi>
         dashboard.noShowRateLabel           -> rate | dashboard.notEnoughData   + dashboard.noShowHelp
         dashboard.unclassifiedLabel         -> <bdi dir="ltr">{confirmed}</bdi> + dashboard.unclassifiedHelp

Card   customers
  <h3>   dashboard.customersHeading
  <p>    dashboard.customersHelp
  <dl>   dashboard.customersTotalLabel · NewLabel · ReturningLabel  -> counts
         dashboard.repeatRateLabel  -> rate | dashboard.notEnoughData  + dashboard.repeatRateHelp

Card   types
  <h3>   dashboard.typesHeading
  <p>    dashboard.typesHelp
  types.length === 0
    <p>  dashboard.typesEmpty
  else
    <table>  caption dashboard.typesTableCaption
      <th scope="col">  dashboard.typeColumn · dashboard.bookingsColumn
      one <tr> per type: <th scope="row"><bdi>{name}</bdi>  <td> bar(count / max) + <bdi dir="ltr">{count}</bdi>
```

**Panel order is forward-first, and it is a decision.** The section is the landing screen for **both** roles, and a shift manager's job is the next seven days, not last quarter. It is also the only panel with a non-zero number on day one — which is the whole load-bearing half of Risk 1's "no `EmptyState`" argument, and that argument is worth nothing if the number it rests on is below twelve zero bars. Declined: history-first (the conventional dashboard order, and it buries the one actionable number under the emptiest panel on the emptiest day).

**Tables, not lists, for the two ranked panels.** Twelve rows × two columns of numbers is a table, and the element does the accessibility work for free: `<th scope="col">` and `<th scope="row">` make every AT announce "תורים שלא בוטלו, 23" without a single `sr-only` sentence per row. A `<ul>` here would need twelve invisible sentences to say the same thing. Two short columns never overflow 375px − gutters, so this does not reintroduce the horizontal scroll that made `manage-staff` a row list.

**`<dl>` for the tiles**, with each `<dt>`/`<dd>` pair wrapped in a `<div>` (valid HTML5, and it is what lets the pairs grid). Sub-lines live **inside the `<dd>`** as `<span className="block">` — a `<p>` between a `<dt>` and a `<dd>` is invalid and axe reports it.

## Rendering rules the builder does not get to choose

**Dates.** `generated_on`, `from_date` and `to_date` are **plain Jerusalem calendar dates on the wire**, not instants. They are formatted by splitting the ISO string — a two-line `plainDate(iso)` added to `lib/jerusalem.ts` beside the existing helpers, with a comment saying so. Passing one through `new Date()` and a zoned formatter is a re-zoning of a date that was never in a zone; it happens to survive today only because Jerusalem is ahead of UTC, and it is exactly the class of bug `lib/jerusalem.ts` exists to prevent. Week-row labels are `d.m` (narrow enough for 375px); the year lives once per panel, in the range line.

**Rates.** One function, and the floor is derived from the precision rather than hand-written:

```
formatRate(r: number | null): string | null
  r === null                  -> null                          // caller renders dashboard.notEnoughData
  s = (r * 100).toFixed(1)
  s === "0.0" && r > 0        -> t("dashboard.rateUnderFloor")  // «פחות מ־0.1%»
  otherwise                   -> `${s}%`
```

Three facts, three renderings: `0.0%` is a true zero, «פחות מ־0.1%» is a non-zero rate the precision cannot show, and `dashboard.notEnoughData` is a `null`. Precision is uniform — `100.0%`, not `100%` — because a mixed rule is more code and one more thing to get wrong. The wire carries the unrounded quotient and the console does all rounding (spec D5).

> ⚠ **Open item for the builder.** The spec's frontend test list asks for "a rate of `0.004` rendering `<0.1%` and not `0%`". `0.004` is **0.4%**, which renders `0.4%` under the one-decimal rule the same spec states — the fixture that actually exercises the floor is `0.0004`. Named rather than silently changed: the spec is authoritative for the rule, and this deck is flagging the fixture.

**Bidi.** Every number, percentage and date is `<bdi dir="ltr">`. Appointment-type names are a **bare** `<bdi>` — `dir="ltr"` on a Hebrew name is itself a bidi defect (`BookPage.tsx:1019-1022`, the rule `manage-staff` records). A range is **one** `<bdi dir="ltr">` around `{from}–{to}` together, not two, because the pair is a single left-to-right run. The one interpolated sentence, `dashboard.summary`, goes through the shipped `isolateLtr` from `lib/booking.tsx` (reused, not re-implemented); its precondition holds — the Hebrew around the placeholder carries no other digits.

**`total`** in the status line is `sum(weeks[].bookings)`, summed client-side. That is arithmetic over numbers already on the wire, not a second definition of anything — the spec asserts `sum(weeks[].bookings) == confirmed + no_show + completed` server-side.

**Colour.** Big KPI numbers are `text-ink` (15.24:1), never gold. `--color-gold-strong` is barred from carrying text by the gold law, and `--color-gold-text` is for links and price emphasis. Gold appears in exactly two places on this screen, both non-text: `SectionHeading`'s `ornament` hairline and the bar fills. Nothing on this screen is signalled by colour at all — there is no status, no threshold, no good/bad. **No number is ever tinted by whether it is "good"**, which is the tell of the generic analytics dashboard and would also make colour the sole carrier of a judgement the product has no basis for.

**Cancellation attribution is two independent counts, never a partition.** `cancelled_by_customer` and `cancelled_by_owner` are rendered as two labelled tiles with no "X of Y" framing and no sum shown, because a row cancelled before migration 0010 carries NULL and is in neither (Risk 11). The design must never imply the two add up to `status_totals.cancelled`.

## Every state

| Screen | State | Treatment |
|---|---|---|
| Section | loading | `<Skeleton variant="text" lines={6} />` — **`variant="text"`, never the default `"block"`**, which is `h-full w-full` and collapses to zero height in a parent with no intrinsic height. One skeleton for the whole section, not five card-shaped ones: the panels' heights depend on data the skeleton does not have, and a skeleton that guesses a shape wrong is worse than a neutral one |
| Section | load failure | one `<p role="alert" className="text-sm text-ink-muted">` — the **outage** register (`dashboard.loadFailed`), no retry control, no code→Hebrew map. The catch sets only `loadError` and deliberately leaves the data state `null`, so no zero-data content can stack under the alert (`BookingsSection.tsx:39-45`). A 403 from an out-of-enum role lands here too, and reads as an outage rather than an accusation |
| Section | loaded | the five Cards, in the order above |
| Section | loaded, whole history zero | the same five Cards, all values `0` or the not-computable sentence, **plus** `dashboard.firstRunNote` under the heading. **No `EmptyState`**, and nothing hidden — see below |
| Status line | loading | `dashboard.loading` |
| Status line | outage | `""` — the alert already speaks; two announcements for one event is one too many |
| Forward | `capacity === 0` | `dashboard.forwardNoHours`, which names **closed hours** and not zero demand, and **no bar** — a bar drawn for a value that does not exist is a lie |
| Forward | `utilization === null` | same treatment; `utilization` is `null` exactly when `capacity` is 0 |
| Weeks | all zero | twelve rows still render, each with a visible empty **track** and a `0`. Zero-fill is a backend guarantee (spec D2) and the design must not collapse it — a chart at zero looks like a chart; eleven missing rows look like a bug |
| Rates / repeat rate | `null` | `dashboard.notEnoughData`, never `0.0%` |
| Types | empty list | one muted `<p>` (`dashboard.typesEmpty`) inside the Card, replacing the table. Not an `EmptyState` block, not a Card full of nothing |

### The empty state is the day-one state, and it is designed

A brand-new boutique is the state a pilot sees on her first login, so it gets the same layout as a busy one, at zero, plus one muted sentence explaining that the screen fills itself. What makes it read as designed rather than broken:

- **Nothing disappears.** Twelve week rows, five tiles, both range lines and the forward panel all render. A screen that sheds panels when data is thin teaches the user that something is wrong.
- **The tracks draw.** Twelve empty hairline tracks read as an instrument at rest. Twelve absent bars read as a failed render.
- **The forward panel is at the top and is usually not zero.** If she has set hours, it shows a real capacity and a real `0.0%` — a fact she can act on. If she has not, `dashboard.forwardNoHours` tells her which section to go set them in, in words.
- **`dashboard.firstRunNote` is one muted `<p>`, not an `EmptyState`.** It hides nothing and replaces nothing; it removes itself the moment any week is non-zero.
- **Zero and unknown are different, visibly.** `0.0%` and «אין עדיין מספיק נתונים לחישוב.» are different strings for different facts, and a day-one boutique sees both on one screen — a true `0.0%` cancellation count is impossible with no bookings, so all three rates read the sentence while the week counts read `0`.

## Edge cases

| Case | Treatment |
|---|---|
| A single booking in the whole window | Its week's bar is **full**, the other eleven are empty tracks, and the count beside it reads `1`. The bar is relative by construction and the number carries the truth; there is no axis promising otherwise. This is why the weeks bars sit beside counts and not percentages |
| `max(weeks[].bookings) === 0` | Every fill is `inlineSize: 0%`. Guarded explicitly — `count / max` with `max === 0` is `NaN`, and `inlineSize: NaN%` is an ignored declaration that silently leaves the previous width in a re-render |
| A tenant with one appointment type | One table row, bar full. Same relative rule, same reason |
| `utilization === 1` (100%) | Fill at `inlineSize: 100%`, reading `100.0%`. The fill is clamped client-side with `Math.min(Math.max(pct, 0), 100)` even though the server already clamps `booked <= capacity` — the clamp is one expression and it is what keeps a contract change from painting outside the track |
| `utilization === 0` with capacity > 0 | Empty track, `0.0%`, and the two counts below read `84` / `0`. Distinct from `capacity === 0`, which shows no bar and the closed-hours sentence |
| A zero week in the middle of a series | Renders as a row with an empty track and `0`, in position. Never skipped, never collapsed |
| Long appointment-type name | The name cell wraps; the bar+count cell keeps its inline size. No truncation, no ellipsis, no `title` attribute — a truncated label with a tooltip is unreachable by touch and by keyboard on a non-interactive cell |
| More than five appointment types | The list simply ends (Risk 14). `dashboard.typesHelp` says the list is the most-booked types and never claims completeness, so the copy is honest at any list length |
| `cancelled_by_customer + cancelled_by_owner < cancelled` | Renders as-is. Two independent counts, no sum, no partition framing (Risk 11) |
| A rate over a handful of appointments | Renders as a percentage, with `dashboard.unclassifiedLabel` beside it carrying the unmarked count and `dashboard.noShowHelp` stating the denominator in words. Risk 5 is bounded by copy, and this is where that copy lives |

## Responsive

`ConsoleShell` caps content at 720px with `px-4` gutters, so 1440 and 768 are the same layout with more air; only 375 changes anything.

| Width | Layout |
|---|---|
| 375 | Everything single-column. Each `<dl>` is one column. Tables are two columns: the label column is `w-16` (`d.m` or a wrapping type name) and the value column takes the rest, so the bar flexes down with the viewport. Nothing scrolls horizontally |
| 768 | Nav becomes ConsoleShell's horizontal row. `<dl>`s go two-up (`sm:grid-cols-2`). Tables unchanged — two columns is already right |
| 1440 | Identical to 768; the 720px cap does the work |

Cards keep their baked-in `p-6`. **Not overridden**: `cn()` is a plain `.filter(Boolean).join(" ")` with no conflict resolution, so a consumer `p-0` and `Card`'s `p-6` are same-specificity rules and the built stylesheet emits `.p-0` first — the override is silently inert. Same finding `manage-staff` and `BookingsSection.tsx:134-137` record.

Bars are `h-2` at every width. They are not a touch target and never become one.

## Accessibility — IS 5568 / WCAG 2.0 AA is a **legal** requirement (pre-decided #38)

The a11y e2e spec asserts zero axe violations, and the vitest axe case is this section's actual proof (spec Testing: the shipped `a11y.spec.ts` cannot reach an authenticated console section).

- **Every visual has a text equivalent, by construction.** Each bar is `aria-hidden` and each value is text in the same row or the same `<dd>`. The design is answerable to a stronger statement than "has alt text": delete every bar and no fact leaves the screen.
- **Heading order.** `ConsoleShell`'s `sr-only` `<h1>` → this section's `<h2>` (via `SectionHeading as="h2"`) → five panel `<h3>`s. No level skipped, no second `h1`, no heading used for size.
- **Tables are real tables.** `<caption class="sr-only">` names each one, `<th scope="col">` heads both columns and `<th scope="row">` heads each row, so every cell is announced with its column word. No `role="table"`, no ARIA grid, no sortable headers — there is no sorting.
- **`<dl>` for the tiles**, so each number is announced with its own term. Sub-lines are inside the `<dd>` they qualify.
- **One announced region**, `role="status"` on the summary line — the loading text and the total, in the one place. It carries **no `tabIndex={-1}`**: `BookingsSection` needs one because a mutation returns focus there, and F52 has no mutation and moves focus nowhere.
- **The outage line is `role="alert"`** and the data state stays `null` behind it, so an AT never gets an outage announcement followed by a screen of zeroes.
- **Keyboard order** is the shell's: skip link → header → eight nav buttons → `<main tabindex="-1">`. Inside the section there is **nothing focusable** — no control, no link, no interactive row. Tab order therefore cannot disagree with visual order, and there is no focus trap and no focus restore to get wrong.
- **Focus rings**: nothing in this section takes focus, so the section adds no ring. The nav row it adds inherits `ConsoleShell`'s shipped `focusRing`.
- **Touch targets**: the section introduces **no target at all**. The one new hit area in F52's blast radius is the eighth `ConsoleShell` nav button, which inherits the shell's existing `py-2 text-base border-b-2` sizing — ≈43.6px, marginally under 44, **for all eight items and shipped that way since F9**. Recorded as an inherited property, not introduced here: raising it moves every console section's nav and belongs to its own change, not to a read-only dashboard.
- **Contrast**, computed not eyeballed: `text-ink` 15.24:1 and `text-ink-muted` 5.61:1 on the card surface, both ≥4.5:1 as text at every size used here. The bar fill's two pairs are stated above. No text on this screen is gold, and none is below `--text-sm`.
- **Colour is never the sole indicator** — and stronger, colour indicates nothing at all here. There is no status colour, no red/green, no threshold tint. Every distinction the screen makes is a word or a number.
- **Motion**: no transitions, no animation, no autoplay. `Skeleton`'s pulse is the only motion and `theme.css` already freezes it under `prefers-reduced-motion`.
- **RTL**: CSS logical properties only — `inlineSize` on the fill, `text-start`, `ms-*`/`me-*`, `gap`. No `left`, `right`, `ml-`, `mr-`, `pl-`, `pr-` or `width` on any directional box. `qa-greps.sh` scopes its physical-property check to `apps/storefront/src`, so `make lint` will **not** catch a violation here — this deck and review are the only guard, which is precisely why it is written down.

## Open items handed to the builder

1. **The `0.004` fixture** (above) renders `0.4%`, not `<0.1%`. The floor fixture is `0.0004`.
2. **The appointment-type fold's predicate is not stated in the spec.** D5 defines `weeks[].bookings` as non-cancelled and D6 defines the customer cohort as non-cancelled, but D6's type fold only says "sum the counts". This deck ships the types table under the **same** column header as the weeks table (`dashboard.bookingsColumn`, «תורים שלא בוטלו»), which requires the service to fold types under the non-cancelled predicate too. Three predicates on one screen would be a defect; if the service folds all four statuses instead, this column needs its own key and the design needs re-reading.

## What this screen deliberately does not have

No date picker, no window selector, no comparison arrow, no period-over-period delta, no sparkline, no legend, no axis, no gridline, no tooltip, no export, no print, no share, no drill-down from a bar into a booking list, no poll, no refresh control, no "last updated" the client computed, no revenue anywhere, and no historical utilization. Each is a spec decision (D2, D4, D8, D11, Out of scope), not an oversight — and every one of them would either add a caller-supplied date to arithmetic that is currently total, or promise a number the schema cannot produce.
