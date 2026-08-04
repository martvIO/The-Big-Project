import type { ReactNode } from "react";
import { render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "../api";
import type { BoutiqueResponse, ExceptionRow, HoursRow } from "../api";
import { StorefrontLayout } from "../components/StorefrontLayout";
import i18n from "../i18n";
import { AboutPage } from "../routes/AboutPage";
import { PRIVACY_FIXTURE } from "../test/boutique";

// /about is the trust surface, and everything on it comes from the ONE
// layout-level getBoutique(). So the route is exercised through StorefrontLayout
// rather than through a per-route fetch stub — mocking a fetch the route no
// longer makes would test nothing.

const { getBoutiqueOnce } = vi.hoisted(() => ({ getBoutiqueOnce: vi.fn() }));

vi.mock("../api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../api")>();
  // Only the layout's single fetch is faked. ApiError and errorMessageOr stay
  // real, so the failure copy asserted below is the copy production renders.
  return { ...actual, getBoutiqueOnce };
});

const NAME = "אטלייה לבן";
const ESSENCE = "שמלות כלה בעבודת יד";
const STORY = "התחלנו בחדר אחד ברחוב דיזנגוף, עם שמלה אחת ושתי ידיים.";
const ADDRESS = "רח׳ דיזנגוף 99, תל אביב";
const MAPS_URL = "https://maps.google.com/?q=dizengoff+99";

const dayLabels = i18n.t("hours.days", { returnObjects: true }) as string[];
const CLOSED = i18n.t("hours.closed");

// Jerusalem Thursday 24.12.2026, 12:00 local. Pinned rather than read from the
// device: the suite runs under TZ=America/New_York on purpose.
const THURSDAY = new Date("2026-12-24T10:00:00Z");
// Jerusalem Sunday 27.12.2026 — the day the lunch-break fixture below opens.
const SUNDAY = new Date("2026-12-27T10:00:00Z");

function boutique(patch: Partial<BoutiqueResponse> = {}): BoutiqueResponse {
  return {
    name: NAME,
    essence: ESSENCE,
    description: STORY,
    phone: "052-1234567",
    address: ADDRESS,
    maps_url: MAPS_URL,
    instagram: "atelier.lavan",
    hours: [
      { day_of_week: 0, open_time: "10:00:00", close_time: "19:00:00" },
      { day_of_week: 1, open_time: "10:00:00", close_time: "19:00:00" },
      { day_of_week: 2, open_time: "10:00:00", close_time: "19:00:00" },
      { day_of_week: 3, open_time: "10:00:00", close_time: "19:00:00" },
      { day_of_week: 4, open_time: "10:00:00", close_time: "19:00:00" },
    ],
    exceptions: [],
    ...PRIVACY_FIXTURE,
    ...patch,
  };
}

function renderAbout(children: ReactNode) {
  return render(<StorefrontLayout>{children}</StorefrontLayout>);
}

// [rowheader text, cell text] for every row HoursTable rendered.
function hoursRows(): [string, string][] {
  return within(screen.getByRole("table"))
    .getAllByRole("row")
    .map((row) => [
      within(row).getByRole("rowheader").textContent ?? "",
      within(row).getByRole("cell").textContent ?? "",
    ]);
}

beforeEach(() => {
  // StorefrontLayout reads the path to decide whether a fixed booking bar is
  // claimed — the default "/" would put the page in the catalog's shape.
  window.history.replaceState(null, "", "/about");
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("AboutPage — load states", () => {
  it("paints skeletons and no alert while the boutique is in flight", () => {
    getBoutiqueOnce.mockReturnValue(new Promise<BoutiqueResponse>(() => undefined));
    const { container } = renderAbout(<AboutPage now={THURSDAY} />);

    // Skeleton is aria-hidden by design, so its animation class is the handle.
    expect(container.querySelectorAll(".animate-skeleton").length).toBeGreaterThan(0);
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: NAME })).not.toBeInTheDocument();
  });

  it("offers Hebrew copy and a retry when the boutique cannot load", async () => {
    getBoutiqueOnce.mockRejectedValue(new ApiError(503, "UNKNOWN", "Service Unavailable"));
    renderAbout(<AboutPage now={THURSDAY} />);

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(i18n.t("about.error"));
    // The server speaks English on a Hebrew-only page — the code selects the
    // key, the message is never rendered.
    expect(alert).not.toHaveTextContent("Service Unavailable");
    expect(screen.getByRole("button", { name: i18n.t("catalog.retry") })).toBeInTheDocument();
  });
});

// The <h1> is where the skip link lands and what orients a screen-reader user.
// axe passes a heading-less page — page-has-heading-one is best-practice, not
// A/AA — so every state is asserted by hand here.
describe("AboutPage — one h1 in every state", () => {
  function soleHeading(): HTMLElement {
    const main = screen.getByRole("main");
    expect(within(main).getAllByRole("heading", { level: 1 })).toHaveLength(1);
    return within(main).getByRole("heading", { level: 1 });
  }

  it("titles the skeleton with the brand fallback while the boutique is in flight", () => {
    getBoutiqueOnce.mockReturnValue(new Promise<BoutiqueResponse>(() => undefined));
    renderAbout(<AboutPage now={THURSDAY} />);

    expect(soleHeading()).toHaveTextContent(i18n.t("catalog.essenceFallback"));
  });

  it("keeps the heading when the boutique fetch fails — not a bare alert and a button", async () => {
    getBoutiqueOnce.mockRejectedValue(new ApiError(503, "UNKNOWN", "Service Unavailable"));
    renderAbout(<AboutPage now={THURSDAY} />);
    await screen.findByRole("alert");

    expect(soleHeading()).toHaveTextContent(i18n.t("catalog.essenceFallback"));
  });

  it("hands the heading over to the boutique's own name once it loads", async () => {
    getBoutiqueOnce.mockResolvedValue(boutique());
    renderAbout(<AboutPage now={THURSDAY} />);
    await screen.findByRole("heading", { level: 1, name: NAME });

    expect(soleHeading()).toHaveTextContent(NAME);
  });
});

describe("AboutPage — the week", () => {
  it("accounts for all seven days when the wire omits Saturday entirely", async () => {
    // Sun–Fri each carry a different closing time so nothing groups — this test
    // is about days being ACCOUNTED FOR, one row each.
    const hours: HoursRow[] = [19, 18, 17, 16, 15, 13].map((closeHour, day) => ({
      day_of_week: day,
      open_time: "10:00:00",
      close_time: `${String(closeHour)}:00:00`,
    }));
    getBoutiqueOnce.mockResolvedValue(boutique({ hours }));
    renderAbout(<AboutPage now={THURSDAY} />);

    await screen.findByRole("heading", { name: i18n.t("about.hoursHeading") });
    const rows = hoursRows();
    expect(rows.map(([day]) => day)).toEqual(dayLabels);
    // Saturday has no rule on the wire: it still renders the literal closed
    // label, never a blank cell and never a dropped row.
    expect(rows[6][1]).toBe(CLOSED);
    expect(rows[5][1]).toBe("10:00–13:00");
  });

  it("does not collapse a range across a day with no rule", async () => {
    // Sun/Mon open, Tue closed, Wed/Thu open, Fri short, Sat closed.
    getBoutiqueOnce.mockResolvedValue(
      boutique({
        hours: [
          { day_of_week: 0, open_time: "10:00:00", close_time: "19:00:00" },
          { day_of_week: 1, open_time: "10:00:00", close_time: "19:00:00" },
          { day_of_week: 3, open_time: "10:00:00", close_time: "19:00:00" },
          { day_of_week: 4, open_time: "10:00:00", close_time: "19:00:00" },
          { day_of_week: 5, open_time: "09:00:00", close_time: "13:00:00" },
        ],
      }),
    );
    renderAbout(<AboutPage now={THURSDAY} />);

    await screen.findByRole("heading", { name: i18n.t("about.hoursHeading") });
    expect(hoursRows()).toEqual([
      [`${dayLabels[0]}–${dayLabels[1]}`, "10:00–19:00"],
      [dayLabels[2], CLOSED],
      [`${dayLabels[3]}–${dayLabels[4]}`, "10:00–19:00"],
      [dayLabels[5], "09:00–13:00"],
      [dayLabels[6], CLOSED],
    ]);
    // A grouper that keys on the window set alone, ignoring adjacency, would
    // advertise the boutique as open on the Tuesday it is shut.
    expect(screen.queryByText(`${dayLabels[0]}–${dayLabels[4]}`)).toBeNull();
  });

  it("renders both windows of a lunch-break day, in the table and in the today line", async () => {
    getBoutiqueOnce.mockResolvedValue(
      boutique({
        hours: [
          { day_of_week: 0, open_time: "10:00:00", close_time: "13:00:00" },
          { day_of_week: 0, open_time: "16:00:00", close_time: "19:00:00" },
        ],
      }),
    );
    renderAbout(<AboutPage now={SUNDAY} />);

    await screen.findByRole("heading", { name: i18n.t("about.hoursHeading") });
    const sunday = within(screen.getByRole("table")).getAllByRole("row")[0];
    // Two separate <bdi> runs: a one-window-per-day model keeps only the last.
    expect(within(sunday).getByText("10:00–13:00")).toBeInTheDocument();
    expect(within(sunday).getByText("16:00–19:00")).toBeInTheDocument();
    expect(
      screen.getByText(i18n.t("about.today", { hours: "10:00–13:00, 16:00–19:00" })),
    ).toBeInTheDocument();
  });

  it("says hours are not published yet — not closed today — when there are no rules at all", async () => {
    getBoutiqueOnce.mockResolvedValue(boutique({ hours: [] }));
    renderAbout(<AboutPage now={THURSDAY} />);

    expect(await screen.findByText(i18n.t("about.hoursUnavailable"))).toBeInTheDocument();
    // A brand-new tenant has entered nothing; announcing a closure it never
    // declared turns a blank profile into a shut door.
    expect(screen.queryByText(i18n.t("about.closedToday"))).toBeNull();
  });
});

describe("AboutPage — exceptions", () => {
  const EXCEPTIONS: ExceptionRow[] = [
    { date: "2026-12-25", open_time: null, close_time: null, note: "חופשה" },
    { date: "2026-12-26", open_time: "09:00:00", close_time: "13:00:00", note: null },
  ];

  it("omits the exceptions row entirely when there are none", async () => {
    getBoutiqueOnce.mockResolvedValue(boutique());
    renderAbout(<AboutPage now={THURSDAY} />);

    await screen.findByRole("heading", { name: i18n.t("about.hoursHeading") });
    expect(screen.queryByText(new RegExp(i18n.t("about.exceptionsLabel")))).toBeNull();
    expect(screen.queryAllByRole("listitem")).toHaveLength(0);
  });

  it("lists both exception shapes with the label as words, not the ◆ marker alone", async () => {
    getBoutiqueOnce.mockResolvedValue(boutique({ exceptions: EXCEPTIONS }));
    renderAbout(<AboutPage now={THURSDAY} />);

    await screen.findByRole("heading", { name: i18n.t("about.hoursHeading") });
    const items = screen.getAllByRole("listitem").map((item) => item.textContent ?? "");
    expect(items).toHaveLength(2);
    // 25.12, not 12.25 — the wire date is already a Jerusalem calendar date.
    expect(items[0]).toContain(i18n.t("about.exceptionClosed", { date: "25.12" }));
    expect(items[0]).toContain("חופשה");
    expect(items[1]).toContain(
      i18n.t("about.exceptionHours", { date: "26.12", open: "09:00", close: "13:00" }),
    );
    for (const item of items) {
      expect(item).toContain(i18n.t("about.exceptionsLabel"));
    }
  });
});

describe("AboutPage — address", () => {
  it("links the address to the map when the owner supplied one", async () => {
    getBoutiqueOnce.mockResolvedValue(boutique());
    renderAbout(<AboutPage now={THURSDAY} />);

    expect(await screen.findByRole("link", { name: ADDRESS })).toHaveAttribute("href", MAPS_URL);
  });

  it("renders the address as plain text when there is no maps_url — never a dead link", async () => {
    getBoutiqueOnce.mockResolvedValue(boutique({ maps_url: null }));
    renderAbout(<AboutPage now={THURSDAY} />);

    // closest("a"), not queryByRole("link"): an <a> with no href has no link
    // role, so a role query passes on the very defect this guards against.
    expect((await screen.findByText(ADDRESS)).closest("a")).toBeNull();
    // The Google Maps contact row goes with it rather than pointing nowhere.
    expect(screen.queryByRole("link", { name: i18n.t("contact.maps") })).not.toBeInTheDocument();
  });
});

describe("AboutPage — booking CTA", () => {
  it("ships one static inline CTA and no fixed bar at any width", async () => {
    getBoutiqueOnce.mockResolvedValue(boutique());
    const { container } = renderAbout(<AboutPage now={THURSDAY} />);

    const cta = await screen.findAllByRole("link", { name: i18n.t("booking.cta") });
    expect(cta).toHaveLength(1);
    // BookingCTA's bar is `fixed inset-x-0 bottom-0` below 768. /about renders
    // nothing of the sort (qa §7) — the A11yMenu is fixed but not full-width,
    // so `.fixed.inset-x-0` isolates the bar itself.
    expect(container.querySelectorAll(".fixed.inset-x-0")).toHaveLength(0);
    expect(cta[0].closest(".fixed")).toBeNull();
  });

  it("navigates into the booking flow rather than opening a panel", async () => {
    getBoutiqueOnce.mockResolvedValue(boutique());
    renderAbout(<AboutPage now={THURSDAY} />);

    // Absolute, and the raw attribute is what matters: the Router's delegated
    // handler pushes anchor.getAttribute("href"), not the resolved .href, so a
    // relative value would be pushed verbatim.
    expect(await screen.findByRole("link", { name: i18n.t("booking.cta") })).toHaveAttribute(
      "href",
      "/book/slot",
    );
  });
});
