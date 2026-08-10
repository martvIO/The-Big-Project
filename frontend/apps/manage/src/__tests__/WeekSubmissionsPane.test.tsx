import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import "../i18n";
import { ApiError, api } from "../api";
import type { ShiftTemplate, WeekSubmissionRow } from "../api";
import { WeekSubmissionsPane } from "../components/WeekSubmissionsPane";

vi.mock("../api", async () => {
  const actual = await vi.importActual<typeof import("../api")>("../api");
  return {
    ...actual,
    api: { ...actual.api, getWeekSubmissions: vi.fn(), submitAvailability: vi.fn() },
  };
});

const getWeekSubmissions = vi.mocked(api.getWeekSubmissions);
const submitAvailability = vi.mocked(api.submitAvailability);

const DANA = "11111111-1111-1111-1111-111111111111";
const MICHAL = "22222222-2222-2222-2222-222222222222";
const MORNING = "33333333-3333-3333-3333-333333333333";
const THURSDAY = "44444444-4444-4444-4444-444444444444";

const WEEK_START = "2026-11-08";
const WEEK_END = "2026-11-14";

// ⚠ TWO TEMPLATES WITH THE SAME LABEL AND THE SAME TIMES, on different weekdays.
// That is the shape D3's auto-labels take the moment the owner splits a day, and
// it is exactly what makes the weekday grouping load-bearing rather than
// decorative.
const TEMPLATES: ShiftTemplate[] = [
  {
    id: MORNING,
    day_of_week: 0,
    label: "משמרת בוקר",
    starts_at_time: "09:00:00",
    ends_at_time: "14:00:00",
    sort_order: 0,
    future_submission_count: 0,
    // F40 D10's sparse map. `{}` is «no target», which is the default
    // state of every template that predates the feature.
    coverage_targets: {},
  },
  {
    id: THURSDAY,
    day_of_week: 4,
    label: "משמרת בוקר",
    starts_at_time: "09:00:00",
    ends_at_time: "14:00:00",
    sort_order: 0,
    future_submission_count: 0,
    // F40 D10's sparse map. `{}` is «no target», which is the default
    // state of every template that predates the feature.
    coverage_targets: {},
  },
];

function row(overrides: Partial<WeekSubmissionRow> = {}): WeekSubmissionRow {
  return {
    staff_user_id: DANA,
    display_name: "דנה כהן",
    submitted: true,
    entries: [
      { id: "e1", shift_template_id: MORNING, state: "available", recorded_by_name: null },
    ],
    ...overrides,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  getWeekSubmissions.mockResolvedValue({
    week_start: WEEK_START,
    week_end: WEEK_END,
    submitted_count: 1,
    total: 2,
    rows: [
      row(),
      row({ staff_user_id: MICHAL, display_name: "מיכל ברזילי", submitted: false, entries: [] }),
    ],
  });
  submitAvailability.mockResolvedValue({
    week_start: WEEK_START,
    week_end: WEEK_END,
    deadline_at: "2026-11-04T16:00:00Z",
    locked: false,
    templates: TEMPLATES,
    entries: [
      { id: "e9", shift_template_id: THURSDAY, state: "preferred", recorded_by_name: "דנה כהן" },
    ],
    // F40 D17: not published, and therefore no shifts of her own.
    roster_published: false,
    rostered_template_ids: [],
  });
});

const mount = () => render(<WeekSubmissionsPane templates={TEMPLATES} />);

describe("the list", () => {
  it("puts the not-yet rows first — that is who the owner opened this to find", async () => {
    mount();
    const names = (await screen.findAllByRole("listitem")).map(
      (item) => item.querySelector("bdi")?.textContent,
    );
    expect(names).toEqual(["מיכל ברזילי", "דנה כהן"]);
  });

  it("counts who started and never announces a fault", async () => {
    // «הגישו 0 מתוך 8» over eight «טרם הגישה» rows is the correct and
    // informative Monday render; an EmptyState here would announce a fault where
    // there is a schedule.
    mount();
    expect(await screen.findByText("הגישו 1 מתוך 2")).toBeInTheDocument();
    expect(screen.getByText("טרם הגישה")).toBeInTheDocument();
    expect(screen.getByText("הגישה")).toBeInTheDocument();
  });

  it("reuses «נענו» verbatim as the per-row progress", async () => {
    // One string measuring the same thing on two panes.
    mount();
    expect(await screen.findByText("נענו: 1 מתוך 2")).toBeInTheDocument();
  });

  it("isolates every display name in a BARE <bdi>", async () => {
    // R19: `dir="ltr"` on a Hebrew name is itself a defect, and three of the
    // four names on this surface are Hebrew.
    mount();
    // The name appears twice per row — once as the row's own label and once
    // inside the expand button's <Trans> island — and BOTH must be bare.
    const islands = await screen.findAllByText("דנה כהן");
    expect(islands).toHaveLength(2);
    for (const island of islands) {
      expect(island.tagName).toBe("BDI");
      expect(island).not.toHaveAttribute("dir");
    }
  });
});

describe("the on-behalf write", () => {
  it("groups the expanded row by weekday, so two identical labels are distinguishable", async () => {
    // ⚠ WITHOUT THIS, a shift manager sees two legends reading «משמרת בוקר ·
    // 09:00–14:00» with nothing distinguishing Sunday from Thursday, and records
    // «לא זמינה» against the wrong day — a write that stamps `recorded_by`
    // permanently and surfaces on the staffer's own screen.
    mount();
    fireEvent.click(await screen.findByRole("button", { name: /רישום עבור מיכל ברזילי/ }));
    expect(await screen.findByRole("heading", { name: "ראשון · 8.11" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "חמישי · 12.11" })).toBeInTheDocument();
    expect(screen.getAllByRole("group")).toHaveLength(2);
  });

  it("tells her the write will carry her name BEFORE the act", async () => {
    // `recorded_by` is about to make it permanent and visible on the staffer's
    // own screen.
    mount();
    fireEvent.click(await screen.findByRole("button", { name: /רישום עבור מיכל ברזילי/ }));
    expect(screen.getByText("הזמינות תירשם על שמך כמי שרשמה אותה.")).toBeInTheDocument();
  });

  it("issues exactly ONE request naming whom to record", async () => {
    // ⚠ NEVER A WRITE PER TAP. D11's `PUT` is a whole-week replace, so a per-tap
    // write would resend her complete entry set on every radio — twelve
    // full-week replaces, twelve audit rows and a race with her own save.
    mount();
    fireEvent.click(await screen.findByRole("button", { name: /רישום עבור מיכל ברזילי/ }));
    const groups = screen.getAllByRole("group");
    fireEvent.click(within(groups[0]).getByRole("radio", { name: "זמינה" }));
    fireEvent.click(within(groups[1]).getByRole("radio", { name: "מעדיפה" }));
    expect(submitAvailability).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: /שמירה עבור מיכל ברזילי/ }));
    await waitFor(() => {
      expect(submitAvailability).toHaveBeenCalledTimes(1);
    });
    expect(submitAvailability).toHaveBeenCalledWith({
      week_start: WEEK_START,
      staff_user_id: MICHAL,
      entries: [
        { shift_template_id: MORNING, state: "available" },
        { shift_template_id: THURSDAY, state: "preferred" },
      ],
    });
  });

  it("flips the badge from the write's own response, with no second read", async () => {
    // F51's patch-don't-refetch: the row we just wrote is the one the server
    // answered with, so a second read could only race it.
    mount();
    fireEvent.click(await screen.findByRole("button", { name: /רישום עבור מיכל ברזילי/ }));
    fireEvent.click(screen.getByRole("button", { name: /שמירה עבור מיכל ברזילי/ }));
    await waitFor(() => {
      expect(screen.getAllByText("הגישה")).toHaveLength(2);
    });
    expect(getWeekSubmissions).toHaveBeenCalledTimes(1);
  });

  it("announces the save with the staffer's name", async () => {
    mount();
    fireEvent.click(await screen.findByRole("button", { name: /רישום עבור מיכל ברזילי/ }));
    fireEvent.click(screen.getByRole("button", { name: /שמירה עבור מיכל ברזילי/ }));
    const cue = await screen.findByRole("status");
    await waitFor(() => {
      expect(screen.getByText(/הזמינות של/)).toBeInTheDocument();
    });
    expect(cue).toBeInTheDocument();
  });

  it("renders a 403 that does NOT claim the action is the owner's alone", async () => {
    // ⚠ ALL THREE SHIPPED `*.error.NOT_AUTHORIZED` STRINGS SAY «לבעלת הבוטיק
    // בלבד», which D5 makes false: a shift manager is admitted to this write.
    submitAvailability.mockRejectedValue(new ApiError(403, "NOT_AUTHORIZED", "english"));
    mount();
    fireEvent.click(await screen.findByRole("button", { name: /רישום עבור מיכל ברזילי/ }));
    fireEvent.click(screen.getByRole("button", { name: /שמירה עבור מיכל ברזילי/ }));
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("אין הרשאה לרשום זמינות עבור אשת צוות אחרת כרגע.");
    expect(alert).not.toHaveTextContent("בלבד");
  });
});

describe("the read", () => {
  it("renders the house load-failure pair and retries on demand", async () => {
    getWeekSubmissions.mockRejectedValueOnce(new Error("boom"));
    mount();
    expect(await screen.findByRole("alert")).toHaveTextContent("לא הצלחנו לטעון את הנתונים כרגע.");
    fireEvent.click(screen.getByRole("button", { name: "ניסיון נוסף" }));
    expect(await screen.findByText("הגישו 1 מתוך 2")).toBeInTheDocument();
  });
});

describe("week navigation", () => {
  it("pages the readiness list the same ±4 weeks her own week pages", async () => {
    // ⚠ WITHOUT THIS THE PANE IS PINNED TO THE SERVER'S DEFAULT WEEK. D1 permits
    // ±4 and `getWeekSubmissions` has always taken the parameter — but with no
    // control on the pane, an owner could only ever read «who has submitted for
    // next week» while `MyWeekPanel` beside her walked four weeks either way.
    mount();
    fireEvent.click(await screen.findByRole("button", { name: "השבוע הבא" }));
    await waitFor(() => {
      expect(getWeekSubmissions).toHaveBeenLastCalledWith("2026-11-15");
    });
    fireEvent.click(screen.getByRole("button", { name: "השבוע הקודם" }));
    await waitFor(() => {
      expect(getWeekSubmissions).toHaveBeenLastCalledWith("2026-11-08");
    });
  });

  it("disables the forward button three weeks past the server's default", async () => {
    // The server's default is NEXT week, so D1's ±4 around the CURRENT week is
    // [-5, +3] around this origin — the identical arithmetic `MyWeekPanel` does,
    // now from one shared pair of constants.
    mount();
    const forward = await screen.findByRole("button", { name: "השבוע הבא" });
    for (let step = 0; step < 3; step += 1) {
      fireEvent.click(screen.getByRole("button", { name: "השבוע הבא" }));
      await waitFor(() => {
        expect(getWeekSubmissions).toHaveBeenCalled();
      });
    }
    await waitFor(() => {
      expect(forward).toBeDisabled();
    });
  });

  it("collapses an expanded row when the week changes", async () => {
    // The pre-filled answers belong to the week she is leaving, and the save
    // button writes `week_start` — so carrying an open form across a week change
    // is how a `recorded_by`-stamped write lands on the wrong week.
    mount();
    fireEvent.click(await screen.findByRole("button", { name: /רישום עבור מיכל ברזילי/ }));
    expect(screen.getByRole("button", { name: /שמירה עבור מיכל ברזילי/ })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "השבוע הבא" }));
    await waitFor(() => {
      expect(
        screen.queryByRole("button", { name: /שמירה עבור מיכל ברזילי/ }),
      ).not.toBeInTheDocument();
    });
  });
});
