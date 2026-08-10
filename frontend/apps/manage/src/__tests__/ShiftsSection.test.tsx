import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import "../i18n";
import { api } from "../api";
import type { ShiftTemplate } from "../api";
import { ShiftsSection } from "../components/ShiftsSection";

vi.mock("../api", async () => {
  const actual = await vi.importActual<typeof import("../api")>("../api");
  return {
    ...actual,
    api: {
      ...actual.api,
      listShiftTemplates: vi.fn(),
      seedShiftTemplates: vi.fn(),
      getShiftWeek: vi.fn(),
      getWeekSubmissions: vi.fn(),
      getSettings: vi.fn(),
    },
  };
});

const listShiftTemplates = vi.mocked(api.listShiftTemplates);
const seedShiftTemplates = vi.mocked(api.seedShiftTemplates);
const getShiftWeek = vi.mocked(api.getShiftWeek);
const getWeekSubmissions = vi.mocked(api.getWeekSubmissions);
const getSettings = vi.mocked(api.getSettings);

const MORNING = "11111111-1111-1111-1111-111111111111";
const WEEK_START = "2026-11-08";

const TEMPLATE: ShiftTemplate = {
  id: MORNING,
  day_of_week: 0,
  label: "משמרת בוקר",
  starts_at_time: "09:00:00",
  ends_at_time: "14:00:00",
  sort_order: 0,
  future_submission_count: 0,
};

beforeEach(() => {
  vi.clearAllMocks();
  listShiftTemplates.mockResolvedValue({ templates: [TEMPLATE] });
  getShiftWeek.mockResolvedValue({
    week_start: WEEK_START,
    week_end: "2026-11-14",
    deadline_at: "2026-11-04T16:00:00Z",
    locked: false,
    templates: [TEMPLATE],
    entries: [],
  });
  getWeekSubmissions.mockResolvedValue({
    week_start: WEEK_START,
    week_end: "2026-11-14",
    submitted_count: 0,
    total: 1,
    rows: [
      { staff_user_id: "s1", display_name: "דנה כהן", submitted: false, entries: [] },
    ],
  });
  getSettings.mockResolvedValue({
    profile: {},
    toggles: {},
    scheduling: { submission_deadline_day_of_week: 3, submission_deadline_time: "18:00" },
  });
});

describe("the pane set", () => {
  it("gives a seamstress exactly one Card — her own week", async () => {
    render(<ShiftsSection role="seamstress" />);
    await screen.findByRole("heading", { name: "הזמינות שלי" });
    expect(screen.getAllByRole("heading", { level: 2 }).map((h) => h.textContent)).toEqual([
      "הזמינות שלי",
    ]);
  });

  it("gives an owner four, her own week FIRST", async () => {
    // One mental model and one e2e path for every role — and an owner who has to
    // scroll past a list she reads first is an owner who stops answering her own
    // week. Configuration last.
    render(<ShiftsSection role="owner" />);
    await screen.findByRole("heading", { name: "מי הגישה" });
    expect(screen.getAllByRole("heading", { level: 2 }).map((h) => h.textContent)).toEqual([
      "הזמינות שלי",
      "מי הגישה",
      "מועד ההגשה",
      "משמרות הבוטיק",
    ]);
  });

  it("gives a shift manager the same four as the owner", async () => {
    // ⚠ D5: she is admitted EVERYWHERE in this feature.
    render(<ShiftsSection role="shift_manager" />);
    await screen.findByRole("heading", { name: "מי הגישה" });
    expect(screen.getAllByRole("heading", { level: 2 })).toHaveLength(4);
  });
});

describe("first run", () => {
  it("shows an elevated actor ONLY the templates Card when none exist", async () => {
    // Three stacked empties above the one button that fixes them is a first-run
    // screen that hides its own next step.
    listShiftTemplates.mockResolvedValue({ templates: [] });
    render(<ShiftsSection role="owner" />);
    await screen.findByRole("button", { name: "יצירת משמרות משעות הפעילות" });
    // ⚠ `waitFor`, NOT A BARE READ AFTER THE SEED BUTTON APPEARS. The collapse is
    // one tick behind that button by construction: the pane renders its own
    // `EmptyState` on the response and reports the list upward in the passive
    // effect that follows, so the container's `if` closes on the NEXT render.
    await waitFor(() => {
      expect(screen.getAllByRole("heading", { level: 2 }).map((h) => h.textContent)).toEqual([
        "משמרות הבוטיק",
      ]);
    });
    // ⚠ THE ASSERTION IS ON THE RENDER, NOT ON THE REQUEST COUNT. §1.2 binds the
    // opposite of a request gate: «while that read is in flight an elevated actor
    // sees the four Cards' skeletons and the collapse to one Card happens on the
    // response». The three panes therefore DO mount and DO start their reads for
    // the length of the templates round-trip, once in a boutique's life — and
    // none of them renders content, which is the thing §1.1 is about. Asserting
    // «never requested» would re-pin the sequential gate that made every
    // staffer's weekly load two round-trips instead of one.
    expect(screen.queryByText("הגישו 0 מתוך 1")).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "מי הגישה" })).not.toBeInTheDocument();
  });

  it("releases the other three panes when the seed succeeds", async () => {
    // ⚠ §5.2: «the other three panes mount for the first time (§1.1's `if`
    // releases)». A container that fetched its OWN templates copy never heard
    // about the seed, so this stayed at one Card until somebody reloaded — the
    // first-run screen permanently stuck on the step it had just completed.
    listShiftTemplates.mockResolvedValue({ templates: [] });
    seedShiftTemplates.mockResolvedValue({ created: 1, templates: [TEMPLATE] });
    render(<ShiftsSection role="owner" />);
    fireEvent.click(await screen.findByRole("button", { name: "יצירת משמרות משעות הפעילות" }));
    await waitFor(() => {
      expect(screen.getAllByRole("heading", { level: 2 }).map((h) => h.textContent)).toEqual([
        "הזמינות שלי",
        "מי הגישה",
        "מועד ההגשה",
        "משמרות הבוטיק",
      ]);
    });
    // And the pane that did the seeding was never remounted under the release,
    // so §5.2's focus destination survives it.
    expect(screen.getByText("משמרות שנוצרו משעות הפעילות: 1")).toBeInTheDocument();
  });

  it("shows a seamstress the empty state and NEVER the seed button", async () => {
    // She cannot fix it, and offering her the seed would be a door that 403s.
    listShiftTemplates.mockResolvedValue({ templates: [] });
    getShiftWeek.mockResolvedValue({
      week_start: WEEK_START,
      week_end: "2026-11-14",
      deadline_at: "2026-11-04T16:00:00Z",
      locked: false,
      templates: [],
      entries: [],
    });
    render(<ShiftsSection role="seamstress" />);
    expect(await screen.findByText("עדיין לא הוגדרו משמרות לשבוע הזה.")).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "יצירת משמרות משעות הפעילות" }),
    ).not.toBeInTheDocument();
  });
});

describe("independence", () => {
  it("leaves an arrived submissions list rendered when another pane's read 500s", async () => {
    // ⚠ NO SHARED «THE SECTION FAILED» STATE. A 500 on the settings read must not
    // blank a readiness list that arrived fine.
    getSettings.mockRejectedValue(new Error("boom"));
    render(<ShiftsSection role="owner" />);
    expect(await screen.findByText("הגישו 0 מתוך 1")).toBeInTheDocument();
    expect(await screen.findByText("טרם הגישה")).toBeInTheDocument();
    // And the failed pane keeps its own heading, so the heading order is
    // unchanged in every state.
    expect(screen.getAllByRole("heading", { level: 2 })).toHaveLength(4);
    await waitFor(() => {
      expect(screen.getAllByRole("alert").length).toBeGreaterThan(0);
    });
  });

  it("confines a failed templates read to its own Card and collapses nothing", async () => {
    // ⚠ REPLACES «offers a retry when the container's own templates read fails».
    // The container has no read of its own to fail: the templates read has one
    // owner and one alert. This asserts MORE than the test it replaces — the
    // other three panes must still render their arrived data (§1.2's «no shared
    // section-failed state»), and a failed read must NOT be mistaken for «no
    // templates exist» and collapse an owner onto the first-run screen.
    listShiftTemplates.mockRejectedValueOnce(new Error("boom"));
    render(<ShiftsSection role="owner" />);
    expect(await screen.findByRole("alert")).toHaveTextContent("לא הצלחנו לטעון את הנתונים כרגע.");
    expect(screen.getByRole("button", { name: "ניסיון נוסף" })).toBeInTheDocument();
    expect(await screen.findByText("הגישו 0 מתוך 1")).toBeInTheDocument();
    expect(screen.getAllByRole("heading", { level: 2 })).toHaveLength(4);
  });

  it("issues the templates read ONCE per elevated mount", async () => {
    // It was issued twice — the container repeated the pane's own read verbatim.
    render(<ShiftsSection role="owner" />);
    await screen.findByRole("heading", { name: "מי הגישה" });
    expect(listShiftTemplates).toHaveBeenCalledTimes(1);
  });

  it("never reads the templates list for a staffer, and never gates her week on one", async () => {
    // ⚠ SHE IS THE HIGHEST-VOLUME USER OF THIS FEATURE by an order of magnitude,
    // and she reads no templates list — hers ride on the week payload. Gating her
    // panel on a container fetch cost her two sequential round-trips every week
    // for a value she never sees.
    render(<ShiftsSection role="seamstress" />);
    await waitFor(() => {
      expect(getShiftWeek).toHaveBeenCalled();
    });
    expect(listShiftTemplates).not.toHaveBeenCalled();
  });
});
