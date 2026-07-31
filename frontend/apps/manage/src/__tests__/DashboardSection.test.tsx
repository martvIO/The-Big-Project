import { render, screen, within } from "@testing-library/react";
import { run } from "axe-core";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import "../i18n";
import type { DashboardResponse, WeekBucket } from "../api";
import { DashboardSection } from "../components/DashboardSection";

vi.mock("../api", async () => {
  const actual = await vi.importActual<typeof import("../api")>("../api");
  return {
    ApiError: actual.ApiError,
    api: { getDashboard: vi.fn() },
  };
});

const { api, ApiError } = await import("../api");
const getDashboard = vi.mocked(api.getDashboard);

// The spec's NORMATIVE payload: generated_on 2026-07-31 (a Friday,
// jerusalem_day_index 5) -> from_date 2026-05-03, to_date 2026-07-25, and the
// last of the twelve buckets starting 2026-07-19. The current in-progress week
// is excluded, which is why to_date < generated_on.
const WEEK_STARTS = [
  "2026-05-03",
  "2026-05-10",
  "2026-05-17",
  "2026-05-24",
  "2026-05-31",
  "2026-06-07",
  "2026-06-14",
  "2026-06-21",
  "2026-06-28",
  "2026-07-05",
  "2026-07-12",
  "2026-07-19",
];

function weeks(counts: readonly number[]): WeekBucket[] {
  return WEEK_STARTS.map((week_start, index) => ({
    week_start,
    bookings: counts[index] ?? 0,
  }));
}

const BUSY_COUNTS = [20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31];
const BUSY_TOTAL = 306;

// Nested overrides rather than a flat Partial: every fixture below varies one
// panel, and the announced total is summed from `weeks` client-side.
function response(
  history: Partial<DashboardResponse["history"]> = {},
  forward: Partial<DashboardResponse["forward"]> = {},
): DashboardResponse {
  return {
    generated_on: "2026-07-31",
    history: {
      from_date: "2026-05-03",
      to_date: "2026-07-25",
      weeks: weeks(BUSY_COUNTS),
      status_totals: { confirmed: 12, cancelled: 9, no_show: 4, completed: 88 },
      // The UNROUNDED quotients the wire actually carries — the console does
      // every bit of the rounding (spec D5).
      cancellation_rate: 9 / 113,
      cancelled_by_customer: 7,
      cancelled_by_owner: 2,
      no_show_rate: 4 / 92,
      appointment_types: [
        { appointment_type_id: "a1", name: "מדידה", bookings: 61 },
        { appointment_type_id: "a2", name: "ייעוץ", bookings: 12 },
      ],
      customers: { total: 74, new: 51, returning: 23, repeat_rate: 23 / 74 },
      ...history,
    },
    forward: {
      from_date: "2026-07-31",
      to_date: "2026-08-06",
      capacity: 84,
      booked: 37,
      utilization: 37 / 84,
      ...forward,
    },
  };
}

const FIRST_RUN_NOTE = "המסך הזה מתמלא מעצמו ככל שנקבעים תורים. עד אז המספרים כאן הם אפס.";

const ZERO_HISTORY: Partial<DashboardResponse["history"]> = {
  weeks: weeks([]),
  status_totals: { confirmed: 0, cancelled: 0, no_show: 0, completed: 0 },
  cancellation_rate: null,
  cancelled_by_customer: 0,
  cancelled_by_owner: 0,
  no_show_rate: null,
  appointment_types: [],
  customers: { total: 0, new: 0, returning: 0, repeat_rate: null },
};

// Day one: no bookings ever, but she HAS set her hours — so the forward panel
// carries a real capacity and a real 0.0%, which is the load-bearing half of
// the "no EmptyState" argument.
function dayOne(): DashboardResponse {
  return response(ZERO_HISTORY, { capacity: 12, booked: 0, utilization: 0 });
}

// DashboardSection renders inside ConsoleShell's <main>, which owns the
// console's single sr-only <h1>. The axe harness reproduces that frame rather
// than scanning a headless fragment.
function renderInShell(node: ReactNode) {
  return render(
    <main>
      <h1 className="sr-only">ניהול הבוטיק</h1>
      {node}
    </main>,
  );
}

function renderSection() {
  return renderInShell(<DashboardSection />);
}

function weeksTable(): HTMLElement {
  return screen.getByRole("table", { name: "תורים שלא בוטלו, לפי שבוע" });
}

function typesTable(): HTMLElement {
  return screen.getByRole("table", { name: "סוגי תורים לפי מספר התורים בתקופה" });
}

// Each <dt>/<dd> pair is wrapped in a <div> so the pairs can grid; that wrapper
// is what scopes an assertion to one tile.
function tile(label: string): HTMLElement {
  const term = screen.getByText(label);
  const pair = term.closest("div");
  if (pair === null) {
    throw new Error(`no <dt>/<dd> wrapper around ${label}`);
  }
  return pair;
}

function panel(heading: string): HTMLElement {
  const title = screen.getByRole("heading", { level: 3, name: heading });
  const card = title.closest("div");
  if (card === null) {
    throw new Error(`no Card around ${heading}`);
  }
  return card;
}

const PANELS = [
  "תפוסה בשבעת הימים הקרובים",
  "תורים לפי שבוע",
  "ביטולים ואי־הגעה",
  "לקוחות בתקופה",
  "סוגי התורים המבוקשים",
];

async function renderLoaded(
  history: Partial<DashboardResponse["history"]> = {},
  forward: Partial<DashboardResponse["forward"]> = {},
) {
  getDashboard.mockResolvedValue(response(history, forward));
  const rendered = renderSection();
  await screen.findByRole("heading", { level: 3, name: PANELS[0] });
  return rendered;
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("DashboardSection states", () => {
  it("announces loading and shows a six-line TEXT skeleton", () => {
    getDashboard.mockReturnValue(new Promise(() => {}));
    const { container } = renderSection();

    expect(screen.getByRole("status")).toHaveTextContent("טוענים את הנתונים.");

    // variant="text", NEVER the default "block": block is h-full w-full and
    // collapses to zero height inside a parent with no intrinsic height.
    const lines = container.querySelectorAll("div[aria-hidden='true'] > span");
    expect(lines).toHaveLength(6);
    expect(lines[0].className).toContain("h-4");
    expect(lines[0].className).not.toContain("h-full");

    expect(screen.queryAllByRole("heading", { level: 3 })).toEqual([]);
  });

  it("fetches exactly once on mount, with no poll and no refetch control", async () => {
    await renderLoaded();
    expect(getDashboard).toHaveBeenCalledTimes(1);
    // Twelve complete past weeks change at most once a week (D11). F51's
    // Risk 3 moves to F34 rather than being closed with an interval here.
    expect(screen.queryAllByRole("button")).toEqual([]);
  });

  it("shows one outage alert with no zero-data content stacked under it", async () => {
    getDashboard.mockRejectedValue(new ApiError(500, "INTERNAL_ERROR", "boom"));
    renderSection();

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "לא הצלחנו לטעון את הנתונים כרגע.",
    );
    // The alert already speaks; two announcements for one event is one too many.
    expect(screen.getByRole("status").textContent).toBe("");
    // The catch deliberately leaves the data state null, so no screen of zeroes
    // can stack under the alert.
    expect(screen.queryAllByRole("heading", { level: 3 })).toEqual([]);
    expect(screen.queryByText("לא נקבעו תורים בתקופה הזו.")).toBeNull();
    expect(screen.queryAllByRole("table")).toEqual([]);
  });

  it("reads a 403 as an outage rather than an accusation", async () => {
    // D10's landing change is what makes NOT_AUTHORIZED reachable here:
    // RoleGate fails closed on a role string the enum does not know, `reachable`
    // is then empty, and `reachable[0]?.key ?? section` lands such a staffer on
    // the dashboard rather than on a 200-ing Profile panel.
    getDashboard.mockRejectedValue(new ApiError(403, "NOT_AUTHORIZED", "Forbidden"));
    renderSection();

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "לא הצלחנו לטעון את הנתונים כרגע.",
    );
    // One string covers any ApiError, which is what keeps the server's verbatim
    // ENGLISH 403 body off the console's landing screen.
    expect(screen.queryByText(/Forbidden/)).toBeNull();
  });

  it("renders the five panels forward-first", async () => {
    await renderLoaded();
    // Forward first is a decision: a shift manager's job is the next seven days,
    // and it is the only panel with a non-zero number on day one.
    expect(screen.getAllByRole("heading", { level: 3 }).map((h) => h.textContent)).toEqual(
      PANELS,
    );
    expect(screen.getByRole("status")).toHaveTextContent(
      `סך התורים שלא בוטלו בתקופה: ${BUSY_TOTAL}`,
    );
    expect(screen.queryByText(FIRST_RUN_NOTE)).toBeNull();
  });

  it("renders the same five panels at zero, with the first-run note and no EmptyState", async () => {
    getDashboard.mockResolvedValue(dayOne());
    renderSection();
    await screen.findByText(FIRST_RUN_NOTE);

    // Nothing disappears: a screen that sheds panels when data is thin teaches
    // the user that something is wrong.
    expect(screen.getAllByRole("heading", { level: 3 }).map((h) => h.textContent)).toEqual(
      PANELS,
    );
    // Twelve rows still render — zero-fill is a backend guarantee and the
    // design must not collapse it.
    expect(within(weeksTable()).getAllByRole("rowheader")).toHaveLength(12);
    // Zero and unknown are different, visibly: all three history rates are null
    // on day one, while the week counts read 0 and the forward panel reads 0.0%.
    expect(screen.getAllByText("אין עדיין מספיק נתונים לחישוב.")).toHaveLength(3);
    expect(within(panel(PANELS[0])).getByText("0.0%")).toBeInTheDocument();
    expect(screen.getByText("לא נקבעו תורים בתקופה הזו.")).toBeInTheDocument();
  });

  // «עד אז המספרים כאן הם אפס» — "until then the numbers here are zero" — is
  // unscoped, and the note renders ABOVE all five cards. weeks[] is the wrong
  // witness for it twice over: it counts only NON-cancelled bookings (D5) and
  // it excludes the current in-progress week entirely (D2).
  it("withholds the first-run note when the forward panel already carries bookings", async () => {
    // A pilot boutique on Wednesday of her FIRST week. Every booking she has
    // lives in the excluded in-progress week and in the next seven days, so all
    // twelve bars are zero while the card under the note reads 12.
    getDashboard.mockResolvedValue(
      response(ZERO_HISTORY, { capacity: 84, booked: 12, utilization: 12 / 84 }),
    );
    renderSection();
    await screen.findByRole("heading", { level: 3, name: PANELS[0] });

    expect(within(tile("מקומות שנתפסו")).getByText("12")).toBeInTheDocument();
    expect(screen.queryByText(FIRST_RUN_NOTE)).toBeNull();
  });

  it("withholds the first-run note when the window's only bookings were cancelled", async () => {
    // Twelve zero bars, and a rates card two lines down reading 100.0%.
    getDashboard.mockResolvedValue(
      response(
        {
          ...ZERO_HISTORY,
          status_totals: { confirmed: 0, cancelled: 5, no_show: 0, completed: 0 },
          cancellation_rate: 1,
          cancelled_by_customer: 5,
        },
        { capacity: 12, booked: 0, utilization: 0 },
      ),
    );
    renderSection();
    await screen.findByRole("heading", { level: 3, name: PANELS[0] });

    expect(within(tile("שיעור הביטולים")).getByText("100.0%")).toBeInTheDocument();
    expect(within(tile("ביטולים ביוזמת הלקוחה")).getByText("5")).toBeInTheDocument();
    expect(screen.queryByText(FIRST_RUN_NOTE)).toBeNull();
  });
});

// Three facts, three strings (copy.md §0 rule 3): a true zero, a non-zero rate
// the precision cannot show, and a null. A screen that collapsed any two would
// tell a pilot boutique it had no cancellations when it had one.
describe("the three rate facts render as three different strings", () => {
  async function cancellationTile(rate: number | null): Promise<HTMLElement> {
    await renderLoaded({ cancellation_rate: rate });
    return tile("שיעור הביטולים");
  }

  it("renders a true zero as 0.0%", async () => {
    expect(within(await cancellationTile(0)).getByText("0.0%")).toBeInTheDocument();
  });

  it("renders a rate below the precision floor as its own string", async () => {
    // 0.0004 is 0.04%, which is "0.0" at one decimal with r > 0 — THE floor
    // case, and the only fixture that reaches that branch.
    const pair = await cancellationTile(0.0004);
    expect(within(pair).getByText("פחות מ־0.1%")).toBeInTheDocument();
    expect(within(pair).queryByText("0.0%")).toBeNull();
  });

  it("renders 0.004 as an ordinary 0.4%, never as the floor string", async () => {
    // 0.004 is 0.4% and never reaches the floor. Its own case, because a floor
    // test whose input does not reach the floor passes under a broken
    // formatRate too.
    const pair = await cancellationTile(0.004);
    expect(within(pair).getByText("0.4%")).toBeInTheDocument();
    expect(within(pair).queryByText("פחות מ־0.1%")).toBeNull();
  });

  it("renders a null rate as the not-computable sentence, never as 0.0%", async () => {
    const pair = await cancellationTile(null);
    expect(within(pair).getByText("אין עדיין מספיק נתונים לחישוב.")).toBeInTheDocument();
    expect(within(pair).queryByText("0.0%")).toBeNull();
  });

  it("rounds the wire's unrounded quotients to one decimal", async () => {
    await renderLoaded();
    expect(within(tile("שיעור הביטולים")).getByText("8.0%")).toBeInTheDocument();
    expect(within(tile("שיעור אי־ההגעה")).getByText("4.3%")).toBeInTheDocument();
    expect(within(tile("שיעור החזרה")).getByText("31.1%")).toBeInTheDocument();
    expect(within(tile("אחוז התפוסה")).getByText("44.0%")).toBeInTheDocument();
  });
});

describe("the bars are decoration and nothing else", () => {
  it("hides every bar from assistive tech", async () => {
    const { container } = await renderLoaded();
    const fills = container.querySelectorAll<HTMLElement>("[style*='inline-size']");
    expect(fills.length).toBeGreaterThan(0);
    for (const fill of fills) {
      expect(fill.closest("[aria-hidden='true']")).not.toBeNull();
    }
  });

  it("grows every fill from the inline-start edge, never with a physical width", async () => {
    const { container } = await renderLoaded();
    const fills = container.querySelectorAll<HTMLElement>("[style*='inline-size']");
    for (const fill of fills) {
      // inlineSize, NOT width: a logical property, so in RTL the fill grows
      // from the inline-start (right) edge.
      expect(fill.style.getPropertyValue("width")).toBe("");
      expect(fill.style.getPropertyValue("inline-size")).toMatch(/^\d+(\.\d+)?%$/);
    }
  });

  it("carries every value a bar draws as text in the same row", async () => {
    // The rule the design is answerable to: remove every bar and the screen
    // loses nothing.
    await renderLoaded();
    for (const count of BUSY_COUNTS) {
      expect(within(weeksTable()).getByText(String(count))).toBeInTheDocument();
    }
    expect(within(typesTable()).getByText("61")).toBeInTheDocument();
    expect(within(typesTable()).getByText("12")).toBeInTheDocument();
    expect(within(tile("אחוז התפוסה")).getByText("44.0%")).toBeInTheDocument();
  });

  it("mounts no progressbar, meter or progress element anywhere", async () => {
    // role="progressbar" announces a task's COMPLETION, not a ratio of a static
    // quantity — an AT would read the utilization bar as an in-flight operation.
    const { container } = await renderLoaded();
    expect(screen.queryAllByRole("progressbar")).toEqual([]);
    expect(screen.queryAllByRole("meter")).toEqual([]);
    expect(container.querySelector("meter, progress")).toBeNull();
  });

  it("draws every fill at 0% and never NaN% when the busiest week is zero", async () => {
    // count / max with max === 0 is NaN, and inline-size: NaN% is an IGNORED
    // declaration that silently leaves the previous width in a re-render.
    getDashboard.mockResolvedValue(dayOne());
    renderSection();
    await screen.findByRole("heading", { level: 3, name: PANELS[1] });

    const fills = weeksTable().querySelectorAll<HTMLElement>("[style*='inline-size']");
    expect(fills).toHaveLength(12);
    for (const fill of fills) {
      expect(fill.style.getPropertyValue("inline-size")).toBe("0%");
    }
  });

  it("draws no bar at all when there are no open hours", async () => {
    // A bar drawn for a value that does not exist is a lie.
    await renderLoaded({}, { capacity: 0, booked: 0, utilization: null });
    await screen.findByText("אין שעות פעילות פתוחות בטווח הזה, ולכן אין כאן מה לחשב.");

    expect(panel(PANELS[0]).querySelectorAll("[style*='inline-size']")).toHaveLength(0);
    expect(screen.queryByText("אחוז התפוסה")).toBeNull();
  });
});

describe("bidi", () => {
  it("isolates every number, percentage and date as an LTR run", async () => {
    await renderLoaded();
    for (const text of ["31.7.2026", "84", "37", "7", "2", "12"]) {
      const node = screen.getAllByText(text)[0];
      expect(node.tagName).toBe("BDI");
      expect(node).toHaveAttribute("dir", "ltr");
    }
  });

  it("wraps a range in ONE bdi around both dates together", async () => {
    await renderLoaded();
    // The pair is a single left-to-right run, so it is one isolate and not two.
    const forwardRange = screen.getByText("31.7.2026–6.8.2026");
    expect(forwardRange.tagName).toBe("BDI");
    expect(forwardRange).toHaveAttribute("dir", "ltr");
    expect(screen.getByText("3.5.2026–25.7.2026").tagName).toBe("BDI");
  });

  it("leaves an appointment-type name in a BARE bdi", async () => {
    await renderLoaded();
    // dir="ltr" on a Hebrew name is itself a bidi defect.
    const name = screen.getByText("מדידה");
    expect(name.tagName).toBe("BDI");
    expect(name).not.toHaveAttribute("dir");
  });
});

describe("the two ranked panels are real tables", () => {
  it("gives the weeks table a caption and scoped headers", async () => {
    await renderLoaded();
    const table = weeksTable();
    expect(within(table).getAllByRole("columnheader").map((h) => h.textContent)).toEqual([
      "תחילת שבוע",
      "תורים שלא בוטלו",
    ]);
    expect(within(table).getAllByRole("rowheader")).toHaveLength(12);
    // The year lives once per panel, in the range line; the row label is d.m.
    expect(within(table).getByText("3.5")).toBeInTheDocument();
    expect(within(table).getByText("19.7")).toBeInTheDocument();
  });

  it("heads the types count column with the SAME predicate as the weeks table", async () => {
    // Two counts, one word: three predicates on one screen would be a defect
    // the owner finds in her first week.
    await renderLoaded();
    expect(within(typesTable()).getAllByRole("columnheader").map((h) => h.textContent)).toEqual(
      ["סוג תור", "תורים שלא בוטלו"],
    );
  });

  it("replaces the types table with one muted line when the list is empty", async () => {
    await renderLoaded({ appointment_types: [] });
    await screen.findByText("לא נקבעו תורים בתקופה הזו.");
    expect(
      screen.queryByRole("table", { name: "סוגי תורים לפי מספר התורים בתקופה" }),
    ).toBeNull();
  });
});

describe("cancellation attribution is never a partition", () => {
  it("renders the two attributions as independent tiles with no sum", async () => {
    // A row cancelled before migration 0010 carries NULL and is in neither, so
    // the two must never be framed as adding up to the cancellation count.
    await renderLoaded({
      status_totals: { confirmed: 12, cancelled: 9, no_show: 4, completed: 88 },
      cancelled_by_customer: 7,
      cancelled_by_owner: 2,
    });
    expect(within(tile("ביטולים ביוזמת הלקוחה")).getByText("7")).toBeInTheDocument();
    expect(within(tile("ביטולים ביוזמת הבוטיק")).getByText("2")).toBeInTheDocument();
    expect(screen.queryByText(/מתוך 9/)).toBeNull();
  });

  it("ships the unclassified count beside the no-show rate", async () => {
    // Risk 5's bound, made visible: an owner who marks three no-shows and
    // nothing else reads 100%, and this is what tells her the denominator.
    await renderLoaded();
    const pair = tile("תורים שעברו ולא סומנו");
    expect(within(pair).getByText("12")).toBeInTheDocument();
    expect(
      within(pair).getByText(
        "תורים שכבר עברו ולא סומנו כהתקיימו או כאי־הגעה. הם אינם נכללים בשיעור אי־ההגעה.",
      ),
    ).toBeInTheDocument();
  });
});

// --- accessibility: IS 5568 / WCAG 2.0 AA is a legal requirement ---

describe("DashboardSection accessibility", () => {
  it("goes h2 then h3 with no skipped level", async () => {
    await renderLoaded();
    expect(screen.getByRole("heading", { level: 2 })).toHaveTextContent("סקירה");
    expect(screen.getAllByRole("heading", { level: 3 })).toHaveLength(5);
  });

  it("announces through one status region that takes no focus", async () => {
    // No tabIndex: BookingsSection needs one because a mutation returns focus
    // there, and this section has no mutation and moves focus nowhere.
    await renderLoaded();
    expect(screen.getByRole("status")).not.toHaveAttribute("tabindex");
  });

  it("passes axe with zero violations on the loaded screen", async () => {
    const { container } = await renderLoaded();
    expect((await run(container)).violations).toEqual([]);
  }, 20000);

  it("passes axe with zero violations on the day-one screen", async () => {
    getDashboard.mockResolvedValue(dayOne());
    const { container } = renderSection();
    await screen.findByRole("heading", { level: 3, name: PANELS[0] });
    expect((await run(container)).violations).toEqual([]);
  }, 20000);

  it("passes axe with zero violations on the outage", async () => {
    getDashboard.mockRejectedValue(new ApiError(500, "INTERNAL_ERROR", "boom"));
    const { container } = renderSection();
    await screen.findByRole("alert");
    expect((await run(container)).violations).toEqual([]);
  }, 20000);
});
