import { describe, expect, it } from "vitest";
import { groupWeeklyRules, jerusalemDayIndex, nextOpen, todayHours } from "../lib/hours";
import type { WeeklyRule } from "../lib/hours";

const w = (open: string, close: string) => ({ open, close });

describe("groupWeeklyRules", () => {
  it("collapses only adjacent identical days, keeps every day, never spans a gap", () => {
    // Binding fixture (qa §6): Sun/Mon/Wed/Thu 10-19, Tue none, Fri 9-13, Sat none.
    const rules: WeeklyRule[] = [
      { dayOfWeek: 0, windows: [w("10:00", "19:00")] },
      { dayOfWeek: 1, windows: [w("10:00", "19:00")] },
      { dayOfWeek: 3, windows: [w("10:00", "19:00")] },
      { dayOfWeek: 4, windows: [w("10:00", "19:00")] },
      { dayOfWeek: 5, windows: [w("09:00", "13:00")] },
    ];
    const rows = groupWeeklyRules(rules);
    expect(rows).toEqual([
      { startDay: 0, endDay: 1, windows: [w("10:00", "19:00")], closed: false },
      { startDay: 2, endDay: 2, windows: [], closed: true },
      { startDay: 3, endDay: 4, windows: [w("10:00", "19:00")], closed: false },
      { startDay: 5, endDay: 5, windows: [w("09:00", "13:00")], closed: false },
      { startDay: 6, endDay: 6, windows: [], closed: true },
    ]);
    // Never one row Sun..Thu — the closed Tuesday breaks the run.
    expect(rows.some((r) => r.startDay === 0 && r.endDay === 4)).toBe(false);
  });

  it("renders a Saturday closed row even when no rule mentions it", () => {
    const rows = groupWeeklyRules([{ dayOfWeek: 0, windows: [w("10:00", "18:00")] }]);
    const sat = rows.find((r) => r.startDay <= 6 && r.endDay >= 6);
    expect(sat?.closed).toBe(true);
  });
});

describe("jerusalemDayIndex", () => {
  it("flips at Jerusalem midnight, not the device clock's (23:00 -> 00:30)", () => {
    const before = new Date("2026-07-24T20:30:00Z"); // 23:30 IDT (UTC+3)
    const after = new Date("2026-07-24T21:30:00Z"); // 00:30 IDT, next day
    const d1 = jerusalemDayIndex(before);
    const d2 = jerusalemDayIndex(after);
    expect(d2).toBe((d1 + 1) % 7);
  });
});

describe("nextOpen", () => {
  const now = new Date("2026-07-24T09:00:00Z");
  const today = jerusalemDayIndex(now);
  const tomorrow = (today + 1) % 7;
  const dayAfter = (today + 2) % 7;

  it("says tomorrow only when the next open day is literally tomorrow", () => {
    const openTomorrow: WeeklyRule[] = [{ dayOfWeek: tomorrow, windows: [w("10:00", "19:00")] }];
    const result = nextOpen(openTomorrow, now);
    expect(result?.isTomorrow).toBe(true);
    expect(result?.daysAhead).toBe(1);
  });

  it("names the real next open day when tomorrow is closed", () => {
    const openDayAfter: WeeklyRule[] = [{ dayOfWeek: dayAfter, windows: [w("10:00", "19:00")] }];
    const result = nextOpen(openDayAfter, now);
    expect(result?.isTomorrow).toBe(false);
    expect(result?.daysAhead).toBe(2);
    expect(result?.dayIndex).toBe(dayAfter);
  });

  it("returns null when the boutique is never open", () => {
    expect(nextOpen([], now)).toBeNull();
  });
});

describe("todayHours", () => {
  it("is closed when today has no rule", () => {
    const now = new Date("2026-07-24T09:00:00Z");
    const other = (jerusalemDayIndex(now) + 3) % 7;
    const result = todayHours([{ dayOfWeek: other, windows: [w("10:00", "19:00")] }], now);
    expect(result.closed).toBe(true);
    expect(result.windows).toEqual([]);
  });
});
