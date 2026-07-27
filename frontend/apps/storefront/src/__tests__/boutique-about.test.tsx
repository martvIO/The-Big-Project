import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { PublicBoutiqueResponse, PublicHoursException } from "../api";
import { BoutiqueAbout } from "../components/BoutiqueAbout";
import i18n from "../i18n";

// BoutiqueAbout takes `now` expressly so a test can pin the weekday. This suite
// is what that seam was built for: the closed-today, reopen and exception
// branches are the ones a visitor to an appointment-only boutique acts on, and
// every other storefront fixture ships `exceptions: []` under an open-every-day
// week, which reaches none of them.
//
// The suite runs under TZ=America/New_York (package.json), so a pass also proves
// the calculation reads Asia/Jerusalem rather than the device.

const SUN_TO_THU = Array.from({ length: 5 }, (_, day) => ({
  day_of_week: day,
  open_time: "10:00:00",
  close_time: "19:00:00",
}));

// Jerusalem Friday. Friday and Saturday carry no weekly rule, so both are closed
// unless an exception opens them.
const FRIDAY = new Date("2026-12-25T10:00:00Z");

function boutique(exceptions: PublicHoursException[] = []): PublicBoutiqueResponse {
  return {
    name: "בוטיק אלמה",
    profile: { phone: "052-1234567", address: null, description: null, maps_url: null },
    rules: SUN_TO_THU,
    exceptions,
  };
}

function exceptionItems(): string[] {
  // HoursTable is a <table>, so the only listitems on the card are the
  // exception rows.
  return screen.getAllByRole("listitem").map((item) => item.textContent ?? "");
}

describe("BoutiqueAbout hours", () => {
  it("names the reopen weekday when tomorrow is closed too", () => {
    render(<BoutiqueAbout boutique={boutique()} now={FRIDAY} />);

    // Friday closed, Saturday closed, so the reopen is Sunday — never "מחר".
    expect(
      screen.getByText(
        `${i18n.t("hours.closedToday")} · ${i18n.t("hours.opensOn", {
          day: i18n.t("hours.day.sun"),
          time: "10:00",
        })}`,
      ),
    ).toBeInTheDocument();
  });

  it("says only closed today when the boutique is never open", () => {
    const never: PublicBoutiqueResponse = { ...boutique(), rules: [] };
    render(<BoutiqueAbout boutique={never} now={FRIDAY} />);

    expect(screen.getByText(i18n.t("hours.closedToday"))).toBeInTheDocument();
  });

  it("reads tomorrow's special hours as the reopen, and lists both exception shapes", () => {
    render(
      <BoutiqueAbout
        boutique={boutique([
          { date: "2026-12-25", open_time: null, close_time: null, note: "חופשה" },
          { date: "2026-12-26", open_time: "09:00:00", close_time: "13:00:00", note: null },
        ])}
        now={FRIDAY}
      />,
    );

    // Saturday is closed by the weekly rules but opened by an exception, so the
    // reopen is literally tomorrow and at the EXCEPTION's time, not 10:00.
    expect(
      screen.getByText(
        `${i18n.t("hours.closedToday")} · ${i18n.t("hours.opensTomorrow", { time: "09:00" })}`,
      ),
    ).toBeInTheDocument();

    const items = exceptionItems();
    expect(items).toHaveLength(2);
    // 25.12, not 12.25 — shortDate is day.month, and the wire date is already a
    // Jerusalem calendar date.
    expect(items[0]).toContain(i18n.t("hours.exceptionClosed", { date: "25.12" }));
    expect(items[0]).toContain("חופשה");
    expect(items[1]).toContain(
      i18n.t("hours.exceptionHours", { date: "26.12", open: "09:00", close: "13:00" }),
    );
    // Every exception carries the label as words, not the ◆ marker alone.
    for (const item of items) {
      expect(item).toContain(i18n.t("hours.exceptionsLabel"));
    }
  });
});
