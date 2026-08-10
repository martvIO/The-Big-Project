import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import "../i18n";
import { api } from "../api";
import type { RosterAssignment, RosterShift, RosterStaffRef, RosterWeek } from "../api";
import { RosterPane } from "../components/RosterPane";

vi.mock("../api", async () => {
  const actual = await vi.importActual<typeof import("../api")>("../api");
  return {
    ...actual,
    api: {
      ...actual.api,
      getRoster: vi.fn(),
      assignToShift: vi.fn(),
      removeAssignment: vi.fn(),
      publishRoster: vi.fn(),
    },
  };
});

const getRoster = vi.mocked(api.getRoster);
const assignToShift = vi.mocked(api.assignToShift);
const removeAssignment = vi.mocked(api.removeAssignment);
const publishRoster = vi.mocked(api.publishRoster);

const MORNING = "11111111-1111-1111-1111-111111111111";
const EVENING = "22222222-2222-2222-2222-222222222222";
const WEEK_START = "2026-11-08";

function template(id: string, day: number, label: string) {
  return {
    id,
    day_of_week: day,
    label,
    starts_at_time: "09:00:00",
    ends_at_time: "14:00:00",
    sort_order: 0,
    future_submission_count: 0,
    coverage_targets: {},
  };
}

function shift(
  id: string,
  day: number,
  label: string,
  overrides: Partial<RosterShift> = {},
): RosterShift {
  return {
    template: template(id, day, label),
    assignments: [],
    coverage_targets: {},
    assigned_by_role: {},
    ...overrides,
  };
}

const DANA: RosterStaffRef = {
  id: "s1",
  display_name: "דנה כהן",
  role: "sales_assistant",
  shift_manager_eligible: true,
  states: {},
};

function assignment(overrides: Partial<RosterAssignment> = {}): RosterAssignment {
  return {
    id: "a1",
    staff_user_id: DANA.id,
    display_name: DANA.display_name,
    role: "sales_assistant",
    is_shift_manager: false,
    override_of_state: null,
    ...overrides,
  };
}

function week(overrides: Partial<RosterWeek> = {}): RosterWeek {
  return {
    week_start: WEEK_START,
    week_end: "2026-11-14",
    published_at: null,
    published_by_name: null,
    edited_since_publish: false,
    shifts: [shift(MORNING, 0, "משמרת בוקר")],
    staff: [DANA],
    ...overrides,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  getRoster.mockResolvedValue(week());
});

const ready = () => screen.findByRole("heading", { level: 2, name: "סידור עבודה" });

describe("the header block", () => {
  it("says «טיוטה» on an unpublished week and names the publisher once published", async () => {
    getRoster.mockResolvedValue(week());
    render(<RosterPane />);
    await ready();
    expect(
      await screen.findByText("טיוטה. הסידור אינו גלוי לצוות ואינו קובע מי במשמרת."),
    ).toBeInTheDocument();

    getRoster.mockResolvedValue(
      week({ published_at: "2026-11-04T16:00:00Z", published_by_name: "רונית בר" }),
    );
    render(<RosterPane />);
    await waitFor(() => {
      expect(screen.getByText(/פורסם על ידי/)).toBeInTheDocument();
    });
    // The name is isolated, and it is NOT in sentence-final position — `<bdi>`
    // isolates a name's interior, it does not move a trailing full stop.
    expect(screen.getByText(/פורסם על ידי/).textContent).toContain("רונית בר");
  });

  it("says «בוצעו שינויים מאז הפרסום» only when the flag is set", async () => {
    getRoster.mockResolvedValue(
      week({ published_at: "2026-11-04T16:00:00Z", published_by_name: "רונית בר" }),
    );
    render(<RosterPane />);
    await ready();
    expect(
      screen.queryByText("בוצעו שינויים מאז הפרסום. הם כבר בתוקף בלוח הקומה."),
    ).not.toBeInTheDocument();

    getRoster.mockResolvedValue(
      week({
        published_at: "2026-11-04T16:00:00Z",
        published_by_name: "רונית בר",
        edited_since_publish: true,
      }),
    );
    render(<RosterPane />);
    expect(
      await screen.findByText("בוצעו שינויים מאז הפרסום. הם כבר בתוקף בלוח הקומה."),
    ).toBeInTheDocument();
  });

  it("names the fresh-boutique manager gap ONCE, never once per shift", async () => {
    getRoster.mockResolvedValue(
      week({
        shifts: [shift(MORNING, 0, "משמרת בוקר"), shift(EVENING, 1, "משמרת ערב")],
        staff: [{ ...DANA, shift_manager_eligible: false }],
      }),
    );
    render(<RosterPane />);
    await ready();
    expect(
      await screen.findAllByText(
        "אף אחת מהצוות אינה מסומנת כמתאימה לניהול משמרת. אפשר לסמן במסך צוות.",
      ),
    ).toHaveLength(1);
  });
});

describe("coverage lines", () => {
  it("reads «חסר איוש» as a WORD when a target is unmet", async () => {
    getRoster.mockResolvedValue(
      week({
        shifts: [
          shift(MORNING, 0, "משמרת בוקר", {
            coverage_targets: { sales_assistant: 2 },
            assigned_by_role: { sales_assistant: 1 },
          }),
        ],
      }),
    );
    render(<RosterPane />);
    await ready();
    expect(await screen.findByText(/יועצת מכירות: 1 מתוך 2/)).toBeInTheDocument();
    expect(screen.getByText("חסר איוש")).toBeInTheDocument();
  });

  it("renders a role with assignments and NO target as a plain count, with no badge", async () => {
    // D10's sparse map on screen: an absent key is «no target», which is not `0`.
    getRoster.mockResolvedValue(
      week({
        shifts: [
          shift(MORNING, 0, "משמרת בוקר", { assigned_by_role: { reception: 1 } }),
        ],
      }),
    );
    render(<RosterPane />);
    await ready();
    expect(await screen.findByText("קבלה: 1")).toBeInTheDocument();
    expect(screen.queryByText("חסר איוש")).not.toBeInTheDocument();
    expect(screen.queryByText(/מתוך/)).not.toBeInTheDocument();
  });

  it("renders a deliberate zero as a target, because absent is not 0", async () => {
    getRoster.mockResolvedValue(
      week({
        shifts: [shift(MORNING, 0, "משמרת בוקר", { coverage_targets: { seamstress: 0 } })],
      }),
    );
    render(<RosterPane />);
    await ready();
    expect(await screen.findByText(/תופרת: 0 מתוך 0/)).toBeInTheDocument();
    expect(screen.queryByText("חסר איוש")).not.toBeInTheDocument();
  });
});

describe("the shortage line and P1", () => {
  const short = () =>
    week({
      shifts: [
        shift(MORNING, 0, "משמרת בוקר", {
          coverage_targets: { sales_assistant: 2 },
          assigned_by_role: { sales_assistant: 1 },
        }),
        shift(EVENING, 1, "משמרת ערב", {
          coverage_targets: { sales_assistant: 1 },
          assigned_by_role: { sales_assistant: 1 },
        }),
      ],
    });

  it("E7 — with no target anywhere, neither the count line nor the checkbox renders", async () => {
    // ⚠ THE GATE IS NOT OPTIONAL. `coverage_targets` ships `{}` by default, so
    // on a boutique that has never set one the «is short» predicate is
    // structurally false forever: ungated, she ticks the box and every weekday
    // section disappears with nothing to distinguish that from a load bug.
    render(<RosterPane />);
    await ready();
    expect(screen.queryByText(/משמרות שחסר בהן איוש:/)).not.toBeInTheDocument();
    expect(screen.queryByText("כל יעדי האיוש מולאו.")).not.toBeInTheDocument();
    expect(
      screen.queryByRole("checkbox", { name: "הצגת משמרות שחסר בהן איוש בלבד" }),
    ).not.toBeInTheDocument();
  });

  it("counts the short shifts, and the count sits ABOVE the publish button", async () => {
    getRoster.mockResolvedValue(short());
    render(<RosterPane />);
    await ready();
    const count = await screen.findByText(/משמרות שחסר בהן איוש: 1/);
    const publish = screen.getByRole("button", { name: "פרסום הסידור" });
    // ⚠ THE DOM ORDER IS §2.7'S ENTIRE SUBSTITUTE FOR A PUBLISH CONFIRMATION.
    // Publish above the count ships the feature with neither.
    expect(count.compareDocumentPosition(publish)).toBe(Node.DOCUMENT_POSITION_FOLLOWING);
  });

  it("adds «מוצגות משמרות…» to the live region on tick and removes it on untick", async () => {
    // ⚠ THE COUNT CANNOT BE THE FILTER'S VOICE: ticking does not change the
    // number, and a region whose text does not change never fires.
    getRoster.mockResolvedValue(short());
    render(<RosterPane />);
    await ready();
    const box = await screen.findByRole("checkbox", {
      name: "הצגת משמרות שחסר בהן איוש בלבד",
    });
    expect(screen.getByText(/משמרות שחסר בהן איוש: 1/).textContent).not.toContain(
      "מוצגות משמרות שחסר בהן איוש בלבד.",
    );
    fireEvent.click(box);
    expect(screen.getByText(/מוצגות משמרות שחסר בהן איוש בלבד\./)).toBeInTheDocument();
    fireEvent.click(box);
    expect(
      screen.queryByText(/מוצגות משמרות שחסר בהן איוש בלבד\./),
    ).not.toBeInTheDocument();
  });

  it("cuts the list to the short shifts, and HOLDS that set across a write", async () => {
    // ⚠ Live filtering unmounts the `<section>` under her open dialog on the
    // write that closes a shortage — focus to `<body>`, the return target gone,
    // and the list reflowing on every single assignment.
    getRoster.mockResolvedValue(short());
    assignToShift.mockResolvedValue(
      shift(MORNING, 0, "משמרת בוקר", {
        assignments: [assignment()],
        coverage_targets: { sales_assistant: 2 },
        assigned_by_role: { sales_assistant: 2 },
      }),
    );
    render(<RosterPane />);
    await ready();
    fireEvent.click(
      await screen.findByRole("checkbox", { name: "הצגת משמרות שחסר בהן איוש בלבד" }),
    );
    expect(screen.getByRole("heading", { level: 4, name: /משמרת בוקר/ })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { level: 4, name: /משמרת ערב/ })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "הוספה למשמרת ראשון · משמרת בוקר" }));
    fireEvent.click(await screen.findByRole("button", { name: "הוספה — דנה כהן" }));
    await waitFor(() => {
      expect(screen.getByText("דנה כהן")).toBeInTheDocument();
    });
    // The shift stopped being short — and it is still on screen, badge gone.
    expect(screen.getByRole("heading", { level: 4, name: /משמרת בוקר/ })).toBeInTheDocument();
    // …while the COUNT updated live, so she watches the number fall without the
    // page moving.
    await waitFor(() => {
      expect(screen.getByText(/כל יעדי האיוש מולאו\./)).toBeInTheDocument();
    });
  });

  it("E6 — filter on with nothing short is a sentence, not a blank pane", async () => {
    getRoster.mockResolvedValue(
      week({
        shifts: [
          shift(MORNING, 0, "משמרת בוקר", {
            coverage_targets: { sales_assistant: 1 },
            assigned_by_role: { sales_assistant: 1 },
          }),
        ],
      }),
    );
    render(<RosterPane />);
    await ready();
    fireEvent.click(
      await screen.findByRole("checkbox", { name: "הצגת משמרות שחסר בהן איוש בלבד" }),
    );
    expect(screen.getByText(/כל יעדי האיוש מולאו\./)).toBeInTheDocument();
    expect(screen.getByText(/מוצגות משמרות שחסר בהן איוש בלבד\./)).toBeInTheDocument();
    expect(screen.queryAllByRole("heading", { level: 3 })).toHaveLength(0);
    expect(
      screen.getByRole("checkbox", { name: "הצגת משמרות שחסר בהן איוש בלבד" }),
    ).toBeChecked();
  });
});

describe("publish", () => {
  it("flips the label and cues on BOTH a first publish and a no-op republish", async () => {
    const published = week({
      published_at: "2026-11-04T16:00:00Z",
      published_by_name: "רונית בר",
    });
    publishRoster.mockResolvedValue(published);
    render(<RosterPane />);
    await ready();
    fireEvent.click(await screen.findByRole("button", { name: "פרסום הסידור" }));
    expect(await screen.findByRole("button", { name: "פרסום מחדש" })).toBeInTheDocument();
    expect(screen.getByText("הסידור פורסם.")).toBeInTheDocument();

    // ⚠ A REPUBLISH THAT CHANGES NOTHING WRITES NOTHING — and still cues.
    // Telling her «nothing happened» when the outcome she wanted is the outcome
    // that holds would be telling her she was wrong when she was right.
    fireEvent.click(screen.getByRole("button", { name: "פרסום מחדש" }));
    await waitFor(() => {
      expect(publishRoster).toHaveBeenCalledTimes(2);
    });
    expect(screen.getByText("הסידור פורסם.")).toBeInTheDocument();
  });
});

describe("the week pager", () => {
  it("disables at the shipped window's edges and clears the pane's transient state", async () => {
    publishRoster.mockResolvedValue(
      week({ published_at: "2026-11-04T16:00:00Z", published_by_name: "רונית בר" }),
    );
    render(<RosterPane />);
    await ready();
    fireEvent.click(await screen.findByRole("button", { name: "פרסום הסידור" }));
    expect(await screen.findByText("הסידור פורסם.")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "השבוע הקודם" }));
    await waitFor(() => {
      expect(getRoster).toHaveBeenCalledWith("2026-11-01");
    });
    // The cue belonged to the week she left.
    expect(screen.queryByText("הסידור פורסם.")).not.toBeInTheDocument();
    // …and the week already in progress says so, from the OFFSET and never from
    // a device clock.
    expect(
      await screen.findByText("השבוע הזה כבר בעיצומו. כל שינוי משפיע על לוח הקומה מיד."),
    ).toBeInTheDocument();
  });

  it("stops at LAST_OFFSET going forward", async () => {
    render(<RosterPane />);
    await ready();
    const next = screen.getByRole("button", { name: "השבוע הבא" });
    for (let i = 0; i < 3; i += 1) {
      fireEvent.click(next);
      await waitFor(() => {
        expect(getRoster).toHaveBeenCalledTimes(i + 2);
      });
    }
    expect(screen.getByRole("button", { name: "השבוע הבא" })).toBeDisabled();
  });
});

describe("failure", () => {
  it("alerts and offers a retry on first render as on retry", async () => {
    getRoster.mockRejectedValueOnce(new Error("boom"));
    render(<RosterPane />);
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "לא הצלחנו לטעון את הנתונים כרגע.",
    );
    // The `h2` survives the failure render, so the heading order never changes.
    expect(screen.getByRole("heading", { level: 2, name: "סידור עבודה" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "ניסיון נוסף" }));
    expect(await screen.findByRole("heading", { level: 4, name: /משמרת בוקר/ })).toBeInTheDocument();
  });
});

describe("the shift block", () => {
  it("names the shift as well as the person on every remove and add control", async () => {
    // ⚠ Dana is on four shifts, so a rotor listing the pane's buttons would
    // otherwise show four identically-named controls.
    getRoster.mockResolvedValue(
      week({
        shifts: [
          shift(MORNING, 0, "משמרת בוקר", { assignments: [assignment()] }),
          shift(EVENING, 1, "משמרת ערב", { assignments: [assignment({ id: "a2" })] }),
        ],
      }),
    );
    render(<RosterPane />);
    await ready();
    expect(
      await screen.findByRole("button", { name: "הסרה — דנה כהן ממשמרת ראשון · משמרת בוקר" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "הסרה — דנה כהן ממשמרת שני · משמרת ערב" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "הוספה למשמרת שני · משמרת ערב" }),
    ).toBeInTheDocument();
  });

  it("renders the override badge from the STAMP and the stale line from the LIVE state", async () => {
    // ⚠ TWO DIFFERENT FACTS, TWO DIFFERENT RENDERS, neither overwriting the
    // other. A build reading only `override_of_state` renders the second as a
    // perfectly healthy shift — and it costs a no-show.
    getRoster.mockResolvedValue(
      week({
        shifts: [
          shift(MORNING, 0, "משמרת בוקר", {
            assignments: [assignment({ override_of_state: "unavailable" })],
          }),
          shift(EVENING, 1, "משמרת ערב", {
            assignments: [assignment({ id: "a2" })],
          }),
        ],
        staff: [{ ...DANA, states: { [EVENING]: "unavailable" } }],
      }),
    );
    render(<RosterPane />);
    await ready();
    expect(await screen.findByText("שובצה בחריגה")).toBeInTheDocument();
    expect(screen.getByText(/סימנה שאינה זמינה אחרי השיבוץ\./)).toBeInTheDocument();
  });

  it("offers the manager slot to eligible staff only, and clear-then-set once filled", async () => {
    getRoster.mockResolvedValue(
      week({
        shifts: [
          shift(MORNING, 0, "משמרת בוקר", {
            assignments: [
              assignment(),
              assignment({ id: "a2", staff_user_id: "s2", display_name: "נועה כץ" }),
            ],
          }),
        ],
        staff: [DANA, { ...DANA, id: "s2", display_name: "נועה כץ", shift_manager_eligible: false }],
      }),
    );
    render(<RosterPane />);
    await ready();
    expect(await screen.findByText("לא נבחרה אחראית משמרת.")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "סימון כאחראית משמרת — דנה כהן" }),
    ).toBeInTheDocument();
    // Not eligible ⇒ no control at all, never a control that 400s.
    expect(
      screen.queryByRole("button", { name: "סימון כאחראית משמרת — נועה כץ" }),
    ).not.toBeInTheDocument();

    assignToShift.mockResolvedValue(
      shift(MORNING, 0, "משמרת בוקר", {
        assignments: [assignment({ is_shift_manager: true })],
      }),
    );
    fireEvent.click(screen.getByRole("button", { name: "סימון כאחראית משמרת — דנה כהן" }));
    await waitFor(() => {
      expect(screen.getByText(/אחראית משמרת:/)).toBeInTheDocument();
    });
    // Filled: only the holder's row has a control, and it CLEARS. Swapping is
    // two deliberate acts, each a single visible write.
    expect(
      screen.getByRole("button", { name: "ביטול הסימון כאחראית משמרת — דנה כהן" }),
    ).toBeInTheDocument();
  });

  it("says «עדיין לא שובצה אף אחת» rather than drawing an EmptyState twelve times", async () => {
    render(<RosterPane />);
    await ready();
    expect(await screen.findByText("עדיין לא שובצה אף אחת למשמרת הזו.")).toBeInTheDocument();
  });
});

describe("F-A — the response-ordering guard", () => {
  it("keeps the LATER write's state when the earlier response arrives second", async () => {
    // ⚠ §2.0 PERMITS TWO CONCURRENT WRITES ON ONE SHIFT BY DESIGN. Without the
    // per-shift ticket, the earlier-issued response arriving second silently
    // drops the later assignment.
    getRoster.mockResolvedValue(
      week({
        shifts: [shift(MORNING, 0, "משמרת בוקר")],
        staff: [DANA, { ...DANA, id: "s2", display_name: "נועה כץ" }],
      }),
    );
    let resolveA = (_: RosterShift) => {};
    let resolveB = (_: RosterShift) => {};
    assignToShift
      .mockImplementationOnce(
        () =>
          new Promise<RosterShift>((resolve) => {
            resolveA = resolve;
          }),
      )
      .mockImplementationOnce(
        () =>
          new Promise<RosterShift>((resolve) => {
            resolveB = resolve;
          }),
      );
    render(<RosterPane />);
    await ready();
    fireEvent.click(await screen.findByRole("button", { name: "הוספה למשמרת ראשון · משמרת בוקר" }));
    fireEvent.click(await screen.findByRole("button", { name: "הוספה — דנה כהן" }));
    fireEvent.click(screen.getByRole("button", { name: "הוספה — נועה כץ" }));
    await waitFor(() => {
      expect(assignToShift).toHaveBeenCalledTimes(2);
    });

    // B resolves first with BOTH names, then A's stale single-name payload
    // arrives — and must be dropped.
    resolveB(
      shift(MORNING, 0, "משמרת בוקר", {
        assignments: [
          assignment(),
          assignment({ id: "a2", staff_user_id: "s2", display_name: "נועה כץ" }),
        ],
      }),
    );

    await waitFor(() => {
      expect(screen.getAllByText("נועה כץ").length).toBeGreaterThan(0);
    });
    resolveA(shift(MORNING, 0, "משמרת בוקר", { assignments: [assignment()] }));
    await waitFor(() => {
      expect(assignToShift).toHaveBeenCalledTimes(2);
    });
    const block = screen.getByRole("heading", { level: 4, name: /משמרת בוקר/ }).parentElement;
    expect(within(block as HTMLElement).getAllByText("נועה כץ").length).toBeGreaterThan(0);
  });
});

describe("every control obeys §2.0", () => {
  it("is size md, with exactly one gold button on the pane", async () => {
    getRoster.mockResolvedValue(
      week({ shifts: [shift(MORNING, 0, "משמרת בוקר", { assignments: [assignment()] })] }),
    );
    render(<RosterPane />);
    await ready();
    await screen.findByRole("heading", { level: 4, name: /משמרת בוקר/ });
    const buttons = screen.getAllByRole("button");
    for (const button of buttons) {
      expect(button).toHaveClass("min-h-11");
    }
    const gold = buttons.filter((button) => button.classList.contains("bg-gold"));
    expect(gold.map((button) => button.textContent)).toEqual(["פרסום הסידור"]);
  });
});

describe("write failures", () => {
  it("maps the 403 to the ROSTER sentence, never to F39's availability one", async () => {
    const { ApiError } = await vi.importActual<typeof import("../api")>("../api");
    removeAssignment.mockRejectedValue(new ApiError(403, "NOT_AUTHORIZED", "nope"));
    getRoster.mockResolvedValue(
      week({ shifts: [shift(MORNING, 0, "משמרת בוקר", { assignments: [assignment()] })] }),
    );
    render(<RosterPane />);
    await ready();
    fireEvent.click(
      await screen.findByRole("button", { name: "הסרה — דנה כהן ממשמרת ראשון · משמרת בוקר" }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "אין הרשאה לבנות או לפרסם סידור עבודה כרגע. לבירור אפשר לפנות לבעלת הבוטיק.",
    );
  });

  it("refetches on a code whose whole meaning is «the screen and the server disagree»", async () => {
    const { ApiError } = await vi.importActual<typeof import("../api")>("../api");
    assignToShift.mockRejectedValue(
      new ApiError(409, "SHIFT_MANAGER_SLOT_TAKEN", "taken"),
    );
    getRoster.mockResolvedValue(
      week({ shifts: [shift(MORNING, 0, "משמרת בוקר", { assignments: [assignment()] })] }),
    );
    render(<RosterPane />);
    await ready();
    fireEvent.click(
      await screen.findByRole("button", { name: "סימון כאחראית משמרת — דנה כהן" }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "כבר שובצה אחראית משמרת למשמרת הזו.",
    );
    await waitFor(() => {
      expect(getRoster).toHaveBeenCalledTimes(2);
    });
  });
});
