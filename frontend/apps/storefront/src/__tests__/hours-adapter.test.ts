import { describe, expect, it } from "vitest";
import type { PublicBoutiqueResponse, PublicHoursException } from "../api";
import i18n from "../i18n";
import { hhmm, shortDate, toExceptions, todayLine, toWeeklyRules } from "../lib/hours-adapter";

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
const SUN_TO_THU = Array.from({ length: 5 }, (_, day) => ({
  day_of_week: day,
  open_time: "10:00:00",
  close_time: "19:00:00",
}));

function boutique(
  rules = SUN_TO_THU,
  exceptions: PublicHoursException[] = [],
): PublicBoutiqueResponse {
  return {
    name: "בוטיק אלמה",
    profile: { phone: null, address: null, description: null, maps_url: null },
    rules,
    exceptions,
  };
}

// Jerusalem weekdays, verified: 24.12.2026 is a Thursday, 25.12 a Friday.
const THURSDAY = new Date("2026-12-24T10:00:00Z");
const FRIDAY = new Date("2026-12-25T10:00:00Z");
// 22:30Z is still Friday 25.12 in New York but already Saturday 26.12 in
// Jerusalem — the instant that tells the two clocks apart.
const SATURDAY_IN_JERUSALEM_FRIDAY_IN_NEW_YORK = new Date("2026-12-25T22:30:00Z");

const t = i18n.t.bind(i18n);

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

describe("toWeeklyRules / toExceptions", () => {
  it("groups several windows on one day into a single rule", () => {
    expect(
      toWeeklyRules([
        { day_of_week: 2, open_time: "10:00:00", close_time: "13:00:00" },
        { day_of_week: 2, open_time: "16:00:00", close_time: "19:00:00" },
      ]),
    ).toEqual([
      {
        dayOfWeek: 2,
        windows: [
          { open: "10:00", close: "13:00" },
          { open: "16:00", close: "19:00" },
        ],
      },
    ]);
  });

  it("keeps a closed-all-day exception as a present key with no windows", () => {
    // The key has to exist even though nothing is pushed — an absent key means
    // "no exception" and falls back to the weekly rule.
    expect(
      toExceptions([{ date: "2026-12-24", open_time: null, close_time: null, note: null }]),
    ).toEqual({ "2026-12-24": [] });
  });
});

describe("todayLine", () => {
  it("reads the open window on a day with a rule", () => {
    expect(todayLine(boutique(), THURSDAY, t)).toBe(
      t("hours.today", { hours: "10:00–19:00" }),
    );
  });

  it("says closed today and names tomorrow when the next open day is literally tomorrow", () => {
    // Saturday in Jerusalem: closed, and Sunday opens the week.
    expect(todayLine(boutique(), SATURDAY_IN_JERUSALEM_FRIDAY_IN_NEW_YORK, t)).toBe(
      `${t("hours.closedToday")} · ${t("hours.opensTomorrow", { time: "10:00" })}`,
    );
  });

  it("names the weekday instead when the next open day is further out", () => {
    // Friday: Saturday is closed too, so the reopen is Sunday — not tomorrow.
    expect(todayLine(boutique(), FRIDAY, t)).toBe(
      `${t("hours.closedToday")} · ${t("hours.opensOn", { day: t("hours.day.sun"), time: "10:00" })}`,
    );
  });

  it("says only closed today when the boutique is never open", () => {
    expect(todayLine(boutique([]), THURSDAY, t)).toBe(t("hours.closedToday"));
  });

  it("lets a closed exception override an otherwise-open weekday", () => {
    const closedThursday = boutique(SUN_TO_THU, [
      { date: "2026-12-24", open_time: null, close_time: null, note: "חופשה" },
    ]);
    // Thursday's tomorrow is Friday, which the weekly rules already close — so
    // the reopen walks on to Sunday rather than stopping at the next calendar day.
    expect(todayLine(closedThursday, THURSDAY, t)).toBe(
      `${t("hours.closedToday")} · ${t("hours.opensOn", { day: t("hours.day.sun"), time: "10:00" })}`,
    );
  });

  it("lets a special-hours exception open an otherwise-closed weekday", () => {
    const openFriday = boutique(SUN_TO_THU, [
      { date: "2026-12-25", open_time: "09:00:00", close_time: "13:00:00", note: null },
    ]);
    expect(todayLine(openFriday, FRIDAY, t)).toBe(t("hours.today", { hours: "09:00–13:00" }));
  });

  it("pushes the reopen past a closed exception rather than landing on it", () => {
    // Sunday is closed by exception, so Friday's reopen is Monday — the branch
    // an "always the next weekly rule" shortcut would get wrong.
    const closedSunday = boutique(SUN_TO_THU, [
      { date: "2026-12-27", open_time: null, close_time: null, note: null },
    ]);
    expect(todayLine(closedSunday, FRIDAY, t)).toBe(
      `${t("hours.closedToday")} · ${t("hours.opensOn", { day: t("hours.day.mon"), time: "10:00" })}`,
    );
  });
});
