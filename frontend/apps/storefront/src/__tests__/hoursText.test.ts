import { describe, expect, it } from "vitest";
import type { BoutiqueResponse, ExceptionRow, HoursRow } from "../api";
import i18n from "../i18n";
import { hhmm, shortDate, toExceptions, todayLine, toWeeklyRules } from "../lib/hoursText";

// For an appointment-only boutique the hours line is the highest-stakes string
// on the page: "סגור היום" when it is open, or a reopen day one off, sends a
// visitor away. The whole module is pure, so every branch is reachable here with
// a pinned instant and no DOM.
//
// The suite runs under TZ=America/New_York (see package.json) — every assertion
// below therefore also proves the calculation reads Asia/Jerusalem and not the
// device clock.

// The classic Israeli boutique week: Sun–Thu open, Friday and Saturday carry no
// rule at all, which lib/hours reads as closed.
const SUN_TO_THU: HoursRow[] = Array.from({ length: 5 }, (_, day) => ({
  day_of_week: day,
  open_time: "10:00:00",
  close_time: "19:00:00",
}));

function boutique(hours: HoursRow[] = SUN_TO_THU, exceptions: ExceptionRow[] = []): BoutiqueResponse {
  return {
    name: "בוטיק אלמה",
    essence: null,
    description: null,
    phone: null,
    address: null,
    maps_url: null,
    instagram: null,
    hours,
    exceptions,
  };
}

// Jerusalem weekdays, verified: 24.12.2026 is a Thursday, 25.12 a Friday.
const THURSDAY = new Date("2026-12-24T10:00:00Z");
const FRIDAY = new Date("2026-12-25T10:00:00Z");
// 22:30Z is still Friday 25.12 in New York but already Saturday 26.12 in
// Jerusalem — the instant that tells the two clocks apart.
const SATURDAY_IN_JERUSALEM_FRIDAY_IN_NEW_YORK = new Date("2026-12-25T22:30:00Z");

const t = i18n.t;
const dayLabels = i18n.t("hours.days", { returnObjects: true }) as string[];

describe("shortDate", () => {
  it("is day.month, never month.day — the ambiguity that would ship silently", () => {
    expect(shortDate("2026-12-25")).toBe("25.12");
  });

  it("drops the leading zeros the wire pads dates with", () => {
    expect(shortDate("2026-04-07")).toBe("7.4");
  });
});

describe("hhmm", () => {
  it("trims the wire's seconds", () => {
    expect(hhmm("09:30:00")).toBe("09:30");
  });
});

describe("toWeeklyRules", () => {
  it("groups two windows on the same day into one rule — a lunch break survives", () => {
    // day_of_week 0 twice: a naive one-to-one map keeps only 16:00–19:00 and
    // silently hides the morning the boutique is actually open.
    expect(
      toWeeklyRules([
        { day_of_week: 0, open_time: "10:00:00", close_time: "13:00:00" },
        { day_of_week: 0, open_time: "16:00:00", close_time: "19:00:00" },
      ]),
    ).toEqual([
      {
        dayOfWeek: 0,
        windows: [
          { open: "10:00", close: "13:00" },
          { open: "16:00", close: "19:00" },
        ],
      },
    ]);
  });

  it("keeps distinct days apart and trims every window's seconds", () => {
    expect(
      toWeeklyRules([
        { day_of_week: 2, open_time: "10:00:00", close_time: "19:00:00" },
        { day_of_week: 5, open_time: "09:00:00", close_time: "13:00:00" },
      ]),
    ).toEqual([
      { dayOfWeek: 2, windows: [{ open: "10:00", close: "19:00" }] },
      { dayOfWeek: 5, windows: [{ open: "09:00", close: "13:00" }] },
    ]);
  });

  it("returns nothing for a boutique that has entered no hours at all", () => {
    expect(toWeeklyRules([])).toEqual([]);
  });
});

describe("toExceptions", () => {
  it("keeps a closed-all-day exception as a present key with no windows", () => {
    // The key has to exist even though nothing is pushed — an absent key means
    // "no exception" and falls back to the weekly rule.
    expect(
      toExceptions([{ date: "2026-12-24", open_time: null, close_time: null, note: null }]),
    ).toEqual({ "2026-12-24": [] });
  });

  it("turns a set open/close pair into one special-hours window", () => {
    expect(
      toExceptions([{ date: "2026-12-26", open_time: "09:00:00", close_time: "13:00:00", note: "ערב חג" }]),
    ).toEqual({ "2026-12-26": [{ open: "09:00", close: "13:00" }] });
  });
});

describe("todayLine", () => {
  it("reads the open window on a day with a rule", () => {
    expect(todayLine(boutique(), THURSDAY, t)).toBe(t("about.today", { hours: "10:00–19:00" }));
  });

  it("says closed today and names tomorrow when the next open day is literally tomorrow", () => {
    // Saturday in Jerusalem: closed, and Sunday opens the week.
    expect(todayLine(boutique(), SATURDAY_IN_JERUSALEM_FRIDAY_IN_NEW_YORK, t)).toBe(
      `${t("about.closedToday")} · ${t("about.opensTomorrow", { time: "10:00" })}`,
    );
  });

  it("names the weekday instead when the next open day is further out", () => {
    // Friday: Saturday is closed too, so the reopen is Sunday — not tomorrow.
    expect(todayLine(boutique(), FRIDAY, t)).toBe(
      `${t("about.closedToday")} · ${t("about.opensOn", { day: dayLabels[0], time: "10:00" })}`,
    );
  });

  it("returns null — not closed-today — when the boutique has no weekly rules", () => {
    // The state every newly provisioned tenant ships in. Rendering "סגור היום"
    // here advertises a closure the owner never entered.
    expect(todayLine(boutique([]), THURSDAY, t)).toBeNull();
  });

  it("lets a closed exception override an otherwise-open weekday", () => {
    const closedThursday = boutique(SUN_TO_THU, [
      { date: "2026-12-24", open_time: null, close_time: null, note: "חופשה" },
    ]);
    // Thursday's tomorrow is Friday, which the weekly rules already close — so
    // the reopen walks on to Sunday rather than stopping at the next calendar day.
    expect(todayLine(closedThursday, THURSDAY, t)).toBe(
      `${t("about.closedToday")} · ${t("about.opensOn", { day: dayLabels[0], time: "10:00" })}`,
    );
  });

  it("lets a special-hours exception open an otherwise-closed weekday", () => {
    const openFriday = boutique(SUN_TO_THU, [
      { date: "2026-12-25", open_time: "09:00:00", close_time: "13:00:00", note: null },
    ]);
    expect(todayLine(openFriday, FRIDAY, t)).toBe(t("about.today", { hours: "09:00–13:00" }));
  });

  it("reads tomorrow's exception hours as the reopen time, not the weekly rule's", () => {
    // Saturday is closed by the weekly rules but opened by an exception, so the
    // reopen is literally tomorrow and at 09:00, not Sunday's 10:00.
    const openSaturday = boutique(SUN_TO_THU, [
      { date: "2026-12-26", open_time: "09:00:00", close_time: "13:00:00", note: null },
    ]);
    expect(todayLine(openSaturday, FRIDAY, t)).toBe(
      `${t("about.closedToday")} · ${t("about.opensTomorrow", { time: "09:00" })}`,
    );
  });

  it("pushes the reopen past a closed exception rather than landing on it", () => {
    // Sunday is closed by exception, so Friday's reopen is Monday — the branch
    // an "always the next weekly rule" shortcut would get wrong.
    const closedSunday = boutique(SUN_TO_THU, [
      { date: "2026-12-27", open_time: null, close_time: null, note: null },
    ]);
    expect(todayLine(closedSunday, FRIDAY, t)).toBe(
      `${t("about.closedToday")} · ${t("about.opensOn", { day: dayLabels[1], time: "10:00" })}`,
    );
  });

  it("joins both windows of a lunch-break day into one today line", () => {
    const lunchBreak = boutique([
      { day_of_week: 4, open_time: "10:00:00", close_time: "13:00:00" },
      { day_of_week: 4, open_time: "16:00:00", close_time: "19:00:00" },
    ]);
    expect(todayLine(lunchBreak, THURSDAY, t)).toBe(
      t("about.today", { hours: "10:00–13:00, 16:00–19:00" }),
    );
  });
});
