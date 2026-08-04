import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import type { SeamstressRef } from "../api";
import {
  capacityMinutes,
  hoursFromMinutes,
  loadMinutes,
  loadRatio,
  overloaded,
  remainingMinutes,
  sortByRemainingCapacity,
  wouldOverload,
} from "../lib/capacity";

// Pure folds over the wire — no DOM, no i18n, no timers. Everything the panel's
// bar, the row's sentence and the assign picker disagree about would disagree
// HERE first, which is the point of the module.

const NOA = "11111111-1111-1111-1111-111111111111";
const DANA = "22222222-2222-2222-2222-222222222222";
const RUTI = "33333333-3333-3333-3333-333333333333";

function row(overrides: Partial<SeamstressRef> = {}): SeamstressRef {
  return {
    id: NOA,
    display_name: "נועה לוי",
    assignable: true,
    weekly_capacity_hours: 12,
    capacity_is_default: false,
    assigned_minutes: 0,
    due_soon_minutes: 0,
    ...overrides,
  };
}

describe("capacityMinutes — the ONE hours-to-minutes conversion in the feature", () => {
  it("multiplies, and keeps null a null", () => {
    // ⚠ THE HOURS/MINUTES CATCHER. The database stores hours
    // (weekly_capacity_hours) and minutes (effort_minutes) and the SERVER never
    // multiplies the two — both units reach the wire under their own names, and
    // this is the only `* 60` on either side of it. A build that divided
    // instead, or forgot the conversion, gives 0.2 or 12 and reds here.
    expect(capacityMinutes(12)).toBe(720);
    // 0 hours is a REAL capacity — she is not available this week — and it is
    // 0 minutes, not "no capacity".
    expect(capacityMinutes(0)).toBe(0);
    expect(capacityMinutes(null)).toBeNull();
  });

  it("is what makes the comparison right, at both sides of one minute", () => {
    // The paired assertion, because `capacityMinutes` alone is arithmetic
    // nobody can misread. A MISSING `* 60` makes 700 > 12 and reddens a healthy
    // row; a `/ 60` makes 721 > 0.2 and does the same. Both are dimensionally
    // plausible on inspection and impossible to miss here.
    expect(overloaded(row({ weekly_capacity_hours: 12, due_soon_minutes: 700 }))).toBe(false);
    expect(overloaded(row({ weekly_capacity_hours: 12, due_soon_minutes: 721 }))).toBe(true);
  });
});

describe("the conversion has ONE site in the console, and this is the grep", () => {
  // The negative half of the unit rule, asserted rather than reviewed. Its twin
  // runs on the server (`no 60 in app/atelier/`), and between them an
  // hours-times-minutes mistake has nowhere to live. A mistake of that shape is
  // wrong by 60× and dimensionally plausible on BOTH sides of the wire, which
  // is why it gets a mechanical check rather than a rule in a document.
  //
  // ⚠ `validation.ts` is the ONE recorded exception and it predates this
  // feature by nine: F15's booking-duration parser converts a wall-clock
  // hh:mm into minutes, a different unit pair on a different surface, and it is
  // scraped by test_frontend_constant_parity.py rather than by this.
  const ALLOWED = new Set(["lib/capacity.ts", "validation.ts"]);

  function sources(dir: string, prefix = ""): [string, string][] {
    const out: [string, string][] = [];
    for (const entry of readdirSync(dir)) {
      const full = join(dir, entry);
      const rel = prefix ? `${prefix}/${entry}` : entry;
      if (statSync(full).isDirectory()) {
        if (entry === "__tests__" || entry === "test" || entry === "assets") {
          continue;
        }
        out.push(...sources(full, rel));
      } else if (entry.endsWith(".ts") || entry.endsWith(".tsx")) {
        out.push([rel, readFileSync(full, "utf8")]);
      }
    }
    return out;
  }

  it("finds no other hours-to-minutes conversion anywhere in the console", () => {
    const offenders = sources(join(__dirname, ".."))
      .filter(([path]) => !ALLOWED.has(path))
      .filter(([, body]) =>
        body
          .split("\n")
          .filter((line) => !line.trimStart().startsWith("//") && !line.trimStart().startsWith("*"))
          .some((line) => /(\*|\/)\s*60\b|\b60\s*(\*|\/)/.test(line)),
      )
      .map(([path]) => path);
    expect(offenders).toEqual([]);
  });
});

describe("loadRatio — the bar's only number", () => {
  it("renders 0 % for an idle configured seamstress", () => {
    expect(loadRatio(row({ weekly_capacity_hours: 12, due_soon_minutes: 0 }))).toBe(0);
  });

  it("renders the true fraction below capacity", () => {
    expect(loadRatio(row({ weekly_capacity_hours: 12, due_soon_minutes: 432 }))).toBe(60);
  });

  it("is FULL AND NOT OVER at exactly capacity", () => {
    // `overloaded` is strictly `>`, so full-and-calm is the honest rendering of
    // a seamstress with exactly a week of work in a week. The colour flips one
    // minute later with NO width change at all.
    const exact = row({ weekly_capacity_hours: 12, due_soon_minutes: 720 });
    expect(loadRatio(exact)).toBe(100);
    expect(overloaded(exact)).toBe(false);
  });

  it("CLAMPS at 100 rather than painting four times outside its track", () => {
    // 400 % is not hypothetical — it is one seamstress and a wedding season.
    // Past 100 % only the colour and the numbers in the sentence move, which is
    // designed: the width answers HOW FULL, the colour answers OVER OR NOT, and
    // the text answers BY HOW MUCH.
    expect(loadRatio(row({ weekly_capacity_hours: 12, due_soon_minutes: 2880 }))).toBe(100);
    expect(loadRatio(row({ weekly_capacity_hours: 12, due_soon_minutes: 1008 }))).toBe(100);
  });

  it("answers NO RATIO for a seamstress with no resolved capacity", () => {
    // Not 0, not 100 — null, and the panel draws NO BAR AT ALL. A bar without a
    // denominator is a picture of a number that does not exist.
    expect(loadRatio(row({ weekly_capacity_hours: null, due_soon_minutes: 240 }))).toBeNull();
  });

  it("answers a finite number when the denominator is zero", () => {
    // ⚠ THE GUARD THAT CANNOT LIVE ONLY IN THE BAR. A raw
    // `due_soon / (0 * 60) * 100` is Infinity, and the shipped Bar's
    // `Number.isFinite(pct) ? … : 0` would then render an EMPTY track for the
    // away-and-drowning seamstress — the exact opposite of the designed
    // rendering. Zero capacity with work is 100: the ratio is undefined, the
    // fact is not.
    expect(loadRatio(row({ weekly_capacity_hours: 0, due_soon_minutes: 360 }))).toBe(100);
    // And zero capacity holding nothing is a consistent state, not an alarm.
    expect(loadRatio(row({ weekly_capacity_hours: 0, due_soon_minutes: 0 }))).toBe(0);
  });

  it("survives a NaN reaching it from the wire", () => {
    // `inline-size: NaN%` is an IGNORED declaration that silently leaves the
    // previous width in place on a re-render — so on a five-second poll a bar
    // could keep a stale width for a whole shift with nothing on screen wrong.
    expect(loadRatio(row({ due_soon_minutes: Number.NaN }))).toBe(0);
  });
});

describe("null capacity and zero capacity render OPPOSITELY", () => {
  it("draws a full red bar for zero and nothing at all for null", () => {
    // ⚠ THE NAMED MUTATION: `if (!row.weekly_capacity_hours) …` collapses these
    // two, rendering the away-and-drowning seamstress as «לא הוגדרה קיבולת»
    // with no bar, no colour and no word.
    const zero = row({ weekly_capacity_hours: 0, due_soon_minutes: 360 });
    const unset = row({ weekly_capacity_hours: null, due_soon_minutes: 360 });

    expect(loadRatio(zero)).toBe(100);
    expect(overloaded(zero)).toBe(true);

    expect(loadRatio(unset)).toBeNull();
    expect(overloaded(unset)).toBe(false);
  });

  it("keeps zero capacity out of the headroom group and null out of the word", () => {
    expect(remainingMinutes(row({ weekly_capacity_hours: 0, due_soon_minutes: 360 }))).toBe(-360);
    expect(remainingMinutes(row({ weekly_capacity_hours: null, due_soon_minutes: 360 }))).toBeNull();
  });
});

describe("loadMinutes — the cue's hypothetical is filtered exactly as the SUM is", () => {
  // ⚠ `due_soon_minutes` is `SUM(effort_minutes) FILTER (WHERE due_date <=
  // horizon)`. Adding a ticket due AFTER `due_soon_through` predicts a number
  // the server will never compute: the cue says «עומס יתר», the next tick
  // leaves her sum untouched, and the bar and the row's sentence both say she
  // is fine — with no colleague and no race. Assignment normally happens at
  // intake, when the due date is weeks out, so it is the COMMON case.
  const THROUGH = "2026-08-11";

  it("counts a ticket due inside the horizon", () => {
    expect(loadMinutes({ effort_minutes: 120, due_date: "2026-08-10" }, THROUGH)).toBe(120);
  });

  it("counts a ticket due ON the horizon — the server's `<=`, not `<`", () => {
    expect(loadMinutes({ effort_minutes: 120, due_date: THROUGH }, THROUGH)).toBe(120);
  });

  it("counts NOTHING for a ticket due one day past it", () => {
    expect(loadMinutes({ effort_minutes: 120, due_date: "2026-08-12" }, THROUGH)).toBe(0);
  });

  it("counts an OVERDUE ticket, exactly as the SQL does", () => {
    // `due_date < today <= horizon` satisfies the FILTER, and the board carries
    // overdue tickets with a live assign control on them.
    expect(loadMinutes({ effort_minutes: 480, due_date: "2026-07-01" }, THROUGH)).toBe(480);
  });

  it("compares the two plain dates lexicographically, across a month and a year edge", () => {
    // Both are the server's `YYYY-MM-DD`, so no `Date` and no `lib/jerusalem`
    // arithmetic — and a zero-padded ISO date sorts as a string.
    expect(loadMinutes({ effort_minutes: 30, due_date: "2026-09-01" }, "2026-08-31")).toBe(0);
    expect(loadMinutes({ effort_minutes: 30, due_date: "2026-12-31" }, "2027-01-02")).toBe(30);
  });
});

describe("wouldOverload — the cue's predicate IS the bar's predicate", () => {
  // One assertion that reds on ANY drift between the two, because a cue
  // predicate that disagrees with the bar is an accessibility regression that
  // leaves the sighted surface correct and passes axe.
  const edges: [string, SeamstressRef][] = [
    ["no capacity resolved", row({ weekly_capacity_hours: null, due_soon_minutes: 360 })],
    ["zero capacity, nothing held", row({ weekly_capacity_hours: 0, due_soon_minutes: 0 })],
    ["zero capacity, work held", row({ weekly_capacity_hours: 0, due_soon_minutes: 360 })],
    ["exactly at capacity", row({ weekly_capacity_hours: 12, due_soon_minutes: 720 })],
    ["one minute over", row({ weekly_capacity_hours: 12, due_soon_minutes: 721 })],
    ["four times over", row({ weekly_capacity_hours: 12, due_soon_minutes: 2880 })],
  ];

  for (const [name, seamstress] of edges) {
    it(`agrees with overloaded() at zero extra minutes — ${name}`, () => {
      expect(wouldOverload(seamstress, 0)).toBe(overloaded(seamstress));
    });
  }

  it("NEVER announces an overload for an unconfigured seamstress", () => {
    // ⚠ THE `null * 60 = 0` CASE. In JS `null * 60` is 0, so a hand-rolled
    // comparison at the assign call site announces «עומס יתר» on EVERY assign
    // to a seamstress nobody has configured — on the one channel a
    // screen-reader user has for this fact — while the bar stays correct.
    expect(wouldOverload(row({ weekly_capacity_hours: null, due_soon_minutes: 0 }), 240)).toBe(
      false,
    );
  });

  it("answers the hypothetical the bar cannot: would THIS ticket push her over", () => {
    const noa = row({ weekly_capacity_hours: 12, due_soon_minutes: 700 });
    expect(overloaded(noa)).toBe(false);
    expect(wouldOverload(noa, 20)).toBe(false); // 720 — exactly at capacity
    expect(wouldOverload(noa, 21)).toBe(true); // 721
    // ⚠ And it does not mutate the row it was asked about.
    expect(noa.due_soon_minutes).toBe(700);
  });
});

describe("hoursFromMinutes — the rendered number never contradicts the word", () => {
  it("rounds UP, so «12 מתוך 12» can never sit beside «עומס יתר»", () => {
    // `overloaded` compares RAW MINUTES, so with Math.round a 721-minute load
    // against a 12 h capacity renders «12 שעות … מתוך 12 · עומס יתר» —
    // displayed numbers saying EQUAL beside a word saying OVER, in the one
    // string that is this feature's entire accessibility payload.
    const capacityHours = 12;
    const cases: [number, boolean][] = [
      [719, false],
      [720, false],
      [721, true],
    ];
    for (const [minutes, over] of cases) {
      const seamstress = row({
        weekly_capacity_hours: capacityHours,
        due_soon_minutes: minutes,
      });
      expect(overloaded(seamstress)).toBe(over);
      const rendered = hoursFromMinutes(minutes);
      // The contradiction, stated as the invariant rather than as three
      // transcribed numbers: the sentence may read EQUAL only when the word is
      // absent.
      expect(rendered === capacityHours && over).toBe(false);
    }
    expect(hoursFromMinutes(721)).toBe(12.1);
    expect(hoursFromMinutes(720)).toBe(12);
    expect(hoursFromMinutes(719)).toBe(12);
  });

  it("renders a whole number for every platform band sum", () => {
    // It never fires with the five shipped bands — all multiples of 30 — which
    // is exactly why it is easy to miss. The settings dialog makes bands any
    // integer in 1..1440 and explicitly not required to be distinct or
    // increasing, so a 37-minute band produces loads at arbitrary offsets.
    expect(hoursFromMinutes(0)).toBe(0);
    expect(hoursFromMinutes(30)).toBe(0.5);
    expect(hoursFromMinutes(360)).toBe(6);
    expect(hoursFromMinutes(2880)).toBe(48);
    // A 37-minute band, twice: 74 minutes is 1.2333… hours and reads «1.3».
    expect(hoursFromMinutes(74)).toBe(1.3);
  });
});

describe("sortByRemainingCapacity — three groups, and the middle one is the point", () => {
  const headroom = row({
    id: DANA,
    display_name: "דנה",
    weekly_capacity_hours: 12,
    due_soon_minutes: 360,
    assigned_minutes: 720,
  }); // remaining +360
  const unconfigured = row({
    id: RUTI,
    display_name: "רותי",
    weekly_capacity_hours: null,
    due_soon_minutes: 240,
    assigned_minutes: 240,
  });
  const over = row({
    id: NOA,
    display_name: "נועה",
    weekly_capacity_hours: 12,
    due_soon_minutes: 900,
    assigned_minutes: 2760,
  }); // remaining -180

  it("ranks known headroom, then unknown, then known overload", () => {
    // ⚠ TWO GROUPS WOULD PUT A 400 % ROW AHEAD OF EVERY UNCONFIGURED ONE. On
    // the state every boutique starts in — some configured, most not — the
    // first option in the picker, the one a hurried shift manager takes, would
    // be the person the panel three inches above is drawing in RED. "Unknown"
    // and "certainly worse than everyone" are not the same rank.
    expect(sortByRemainingCapacity([over, unconfigured, headroom]).map((r) => r.display_name)).toEqual(
      ["דנה", "רותי", "נועה"],
    );
  });

  it("orders real headroom by the biggest gap first", () => {
    const small = row({ id: DANA, display_name: "דנה", weekly_capacity_hours: 12, due_soon_minutes: 660 });
    const large = row({ id: RUTI, display_name: "רותי", weekly_capacity_hours: 40, due_soon_minutes: 60 });
    expect(sortByRemainingCapacity([small, large]).map((r) => r.display_name)).toEqual([
      "רותי",
      "דנה",
    ]);
  });

  it("orders the UNCONFIGURED group by what she is already holding, ascending", () => {
    // ⚠ `assigned_minutes` and NOT `due_soon_minutes`, because «{{hours}} שעות
    // משויכות» is the number the option and the panel row actually DISPLAY for
    // this group. A group ordered by a number neither surface shows is the
    // invisible rule this whole sort exists to avoid.
    const busy = row({
      id: DANA,
      display_name: "דנה",
      weekly_capacity_hours: null,
      assigned_minutes: 600,
      due_soon_minutes: 0,
    });
    const light = row({
      id: RUTI,
      display_name: "רותי",
      weekly_capacity_hours: null,
      assigned_minutes: 120,
      due_soon_minutes: 600,
    });
    expect(sortByRemainingCapacity([busy, light]).map((r) => r.display_name)).toEqual([
      "רותי",
      "דנה",
    ]);
  });

  it("orders the overloaded group least-over first", () => {
    const barely = row({ id: DANA, display_name: "דנה", weekly_capacity_hours: 12, due_soon_minutes: 740 });
    const drowning = row({ id: RUTI, display_name: "רותי", weekly_capacity_hours: 12, due_soon_minutes: 2880 });
    expect(sortByRemainingCapacity([drowning, barely]).map((r) => r.display_name)).toEqual([
      "דנה",
      "רותי",
    ]);
  });

  it("puts a ZERO-capacity row holding work in group 3, never group 1", () => {
    // ⚠ Truthiness in the resolution would put her FIRST — the seamstress
    // configured as unavailable, recommended above a colleague with room.
    const away = row({
      id: NOA,
      display_name: "יעל",
      weekly_capacity_hours: 0,
      due_soon_minutes: 360,
    });
    expect(
      sortByRemainingCapacity([away, unconfigured, headroom]).map((r) => r.display_name),
    ).toEqual(["דנה", "רותי", "יעל"]);
  });

  it("breaks every tie by display_name and then by id", () => {
    const first = row({ id: DANA, display_name: "אביגיל", weekly_capacity_hours: 12, due_soon_minutes: 360 });
    const second = row({ id: NOA, display_name: "בת אל", weekly_capacity_hours: 12, due_soon_minutes: 360 });
    const twin = row({ id: RUTI, display_name: "אביגיל", weekly_capacity_hours: 12, due_soon_minutes: 360 });
    expect(sortByRemainingCapacity([second, twin, first]).map((r) => r.id)).toEqual([
      DANA,
      RUTI,
      NOA,
    ]);
  });

  it("does not mutate the array it was handed", () => {
    // The console holds the SERVER's order — `display_name, id` — and the sort
    // is a render-time fold. Mutating in place would hand every other consumer
    // an order it did not ask for, including the payload the truncation
    // boundary was computed against.
    const input = [over, unconfigured, headroom];
    const before = [...input];
    sortByRemainingCapacity(input);
    expect(input).toEqual(before);
  });
});
