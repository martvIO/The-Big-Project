// The bidi presenter for a formatted date range, shared by F28's reservations
// pane and F39's week bar.
//
// It lives in `lib/` rather than in either component for `lib/booking.tsx`'s
// stated reason: a helper hung off one of two consumers points the import arrow
// at a component, and the second consumer then either imports a sibling
// component or grows a second copy. `formatDateRange` itself stays in
// `@boutique/ui` — it is UTC-parsed and unit-tested under
// TZ=America/New_York precisely so a naive re-implementation reds outside
// Israel, and F39 imports it rather than re-deriving anything.
import type { FormattedDateRange } from "@boutique/ui";

// One numeral run gets one island; two whole dates get one each, with the dash
// in RTL flow between them (R19's split shape). dir="ltr" belongs on the pure
// numeral run only — a split part carries its own Hebrew month, and an LTR base
// direction reorders it, so «28 באוגוסט» renders as «באוגוסט 28». Bare <bdi>
// infers RTL from the month.
//
// ⚠ BOTH SHAPES ARE REAL ON F39's WEEK BAR, roughly once a month: a Sunday-start
// week that crosses a month boundary («29 בנובמבר – 5 בדצמבר») is the `split`
// case, and every other week is `same-month` («8–14 בנובמבר»). A component that
// renders only the first is correct for three weeks in four.
export function RangeText({ range }: { range: FormattedDateRange }) {
  if (range.kind === "same-month") {
    return (
      <>
        <bdi dir="ltr">{range.days}</bdi> {range.month}
      </>
    );
  }
  return (
    <>
      <bdi>{range.start}</bdi> – <bdi>{range.end}</bdi>
    </>
  );
}

// ⚠ `rangeToText` DELIBERATELY DID NOT MOVE HERE. It flattens a range for an
// `aria-label`, it has exactly one consumer (`ReservationsPane`'s delete
// button), and F39 does not need it — its week range is visible text in a
// `role="status"` line. Exporting a non-component beside a component here would
// also cost the file `react/only-export-components`, which nothing else in this
// tree carries.
