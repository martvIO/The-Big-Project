import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import "../i18n";
import type { RosterAssignment, RosterStaffRef, ShiftTemplate } from "../api";
import { RosterCellDialog } from "../components/RosterCellDialog";

// ⚠ NO FOCUS ASSERTIONS IN THIS FILE. jsdom has no `<dialog>` and `setup.ts`
// stubs `showModal()`, so an assertion that pre-places focus on its own target
// is vacuous (`.memory/jsdom-has-no-dialog`). This file asserts CONTENT — the
// sort, the copy, the payload, the arming rules — and real focus behaviour
// belongs to the e2e leg.

const MORNING = "11111111-1111-1111-1111-111111111111";

const TEMPLATE: ShiftTemplate = {
  id: MORNING,
  day_of_week: 0,
  label: "משמרת בוקר",
  starts_at_time: "09:00:00",
  ends_at_time: "14:00:00",
  sort_order: 0,
  future_submission_count: 0,
  coverage_targets: {},
};

function person(
  id: string,
  display_name: string,
  state?: "preferred" | "available" | "unavailable",
): RosterStaffRef {
  return {
    id,
    display_name,
    role: "sales_assistant",
    shift_manager_eligible: false,
    states: state === undefined ? {} : { [MORNING]: state },
  };
}

// Deliberately declared in an order that is NOT the render order, so the sort is
// proved rather than inherited from the fixture.
const DANA = person("s1", "דנה כהן", "available");
const MICHAL = person("s2", "מיכל ברזילי", "unavailable");
const NOA = person("s3", "נועה כץ");
const SHIRA = person("s4", "שירה לוי", "preferred");
const RONIT = person("s5", "Ronit Bar", "available");

const ASSIGNED: RosterAssignment = {
  id: "a1",
  staff_user_id: RONIT.id,
  display_name: RONIT.display_name,
  role: "sales_assistant",
  is_shift_manager: false,
  override_of_state: null,
};

let onAssign: ReturnType<typeof vi.fn>;
let onRemove: ReturnType<typeof vi.fn>;

function mount(overrides: {
  assignments?: RosterAssignment[];
  staff?: RosterStaffRef[];
  weekCounts?: Record<string, number>;
  error?: string | null;
} = {}) {
  return render(
    <RosterCellDialog
      open
      onClose={() => {}}
      dayName="ראשון"
      template={TEMPLATE}
      assignments={overrides.assignments ?? []}
      staff={overrides.staff ?? [DANA, MICHAL, NOA, SHIRA, RONIT]}
      weekCounts={overrides.weekCounts ?? {}}
      error={overrides.error ?? null}
      onAssign={onAssign as never}
      onRemove={onRemove as never}
    />,
  );
}

beforeEach(() => {
  onAssign = vi.fn().mockResolvedValue(true);
  onRemove = vi.fn().mockResolvedValue(true);
});

const names = () => screen.getAllByRole("listitem").map((li) => li.querySelector("bdi")?.textContent);

describe("the sort is the design", () => {
  it("puts assigned first, then preferred → available → not answered → unavailable", () => {
    mount({ assignments: [ASSIGNED] });
    expect(names()).toEqual([
      "Ronit Bar", // assigned
      "שירה לוי", // preferred
      "דנה כהן", // available
      "נועה כץ", // not answered
      "מיכל ברזילי", // unavailable
    ]);
  });

  it("is stable in the server's staff order inside a bucket", () => {
    // Two `available` colleagues keep the order the server sent, so the list
    // does not reshuffle from shift to shift.
    mount({ staff: [RONIT, DANA] });
    expect(names()).toEqual(["Ronit Bar", "דנה כהן"]);
  });
});

describe("her state is a word", () => {
  it("says «לא נרשם» for this shift, never «טרם הגישה»", () => {
    // ⚠ «טרם הגישה» is a fact about the PERSON and it is WeekSubmissionsPane's
    // badge. Here the fact is about THIS SHIFT: a staffer who answered eleven of
    // twelve and left this one blank has emphatically «הגישה».
    mount({ staff: [NOA] });
    expect(screen.getByText("לא נרשם")).toBeInTheDocument();
    expect(screen.queryByText("טרם הגישה")).not.toBeInTheDocument();
  });

  it("marks an assigned row «שובצה» rather than repeating her answer", () => {
    mount({ assignments: [ASSIGNED], staff: [RONIT] });
    expect(screen.getByText("שובצה")).toBeInTheDocument();
  });
});

describe("the week count", () => {
  it("is a count of SHIFTS, on every row, and 0 when she holds none", () => {
    mount({ staff: [DANA, NOA], weekCounts: { s1: 3 } });
    expect(screen.getByText("שובצה השבוע: 3")).toBeInTheDocument();
    expect(screen.getByText("שובצה השבוע: 0")).toBeInTheDocument();
    // §0.3: never hours, no total, no threshold.
    expect(screen.queryByText(/שעות/)).not.toBeInTheDocument();
  });
});

describe("assigning against «לא זמינה»", () => {
  it("writes NOTHING on the first tap and shows the warning in the row itself", () => {
    mount({ staff: [MICHAL] });
    fireEvent.click(screen.getByRole("button", { name: "הוספה — מיכל ברזילי" }));
    expect(onAssign).not.toHaveBeenCalled();
    // ⚠ IN THE ROW, not in the dialog's top region: a warning painted above her
    // scroll position while the changed button is under her finger is a label
    // change with no visible reason.
    const row = screen.getByRole("listitem");
    expect(within(row).getByRole("status")).toHaveTextContent(
      "מיכל ברזילי סימנה שאינה זמינה במשמרת הזו. השיבוץ יירשם כחריגה.",
    );
    expect(screen.getByRole("button", { name: "שיבוץ בכל זאת" })).toBeInTheDocument();
  });

  it("sends acknowledge_override on the second tap", async () => {
    mount({ staff: [MICHAL] });
    fireEvent.click(screen.getByRole("button", { name: "הוספה — מיכל ברזילי" }));
    fireEvent.click(screen.getByRole("button", { name: "שיבוץ בכל זאת" }));
    await waitFor(() => {
      expect(onAssign).toHaveBeenCalledWith("s2", true);
    });
  });

  it("sends no acknowledgement on a row that needs none", async () => {
    mount({ staff: [DANA] });
    fireEvent.click(screen.getByRole("button", { name: "הוספה — דנה כהן" }));
    await waitFor(() => {
      expect(onAssign).toHaveBeenCalledWith("s1", false);
    });
  });

  it("arms at most one row — a second tap elsewhere clears the first", () => {
    const other = person("s6", "רות לוי", "unavailable");
    mount({ staff: [MICHAL, other] });
    fireEvent.click(screen.getByRole("button", { name: "הוספה — מיכל ברזילי" }));
    fireEvent.click(screen.getByRole("button", { name: "הוספה — רות לוי" }));
    expect(screen.getAllByRole("button", { name: "שיבוץ בכל זאת" })).toHaveLength(1);
    expect(screen.getByRole("button", { name: "הוספה — מיכל ברזילי" })).toBeInTheDocument();
  });

  it("names the shift nobody can cover BEFORE she reads eight names", () => {
    mount({ staff: [MICHAL, person("s6", "רות לוי", "unavailable")] });
    expect(screen.getByText("כל מי שהגישה סימנה שאינה זמינה במשמרת הזו.")).toBeInTheDocument();
  });

  it("keeps that line off a shift somebody can cover", () => {
    mount({ staff: [MICHAL, DANA] });
    expect(
      screen.queryByText("כל מי שהגישה סימנה שאינה זמינה במשמרת הזו."),
    ).not.toBeInTheDocument();
  });
});

describe("the cue", () => {
  it("announces the assignment, and the removal, in the top region", async () => {
    mount({ assignments: [ASSIGNED], staff: [RONIT, DANA] });
    fireEvent.click(screen.getByRole("button", { name: "הוספה — דנה כהן" }));
    await waitFor(() => {
      expect(screen.getByRole("status")).toHaveTextContent("דנה כהן שובצה למשמרת.");
    });
    fireEvent.click(screen.getByRole("button", { name: "הסרה — Ronit Bar" }));
    await waitFor(() => {
      expect(screen.getByRole("status")).toHaveTextContent("Ronit Bar הוסרה מהמשמרת.");
    });
  });

  it("stays silent when the write is refused", async () => {
    onAssign.mockResolvedValue(false);
    mount({ staff: [DANA] });
    fireEvent.click(screen.getByRole("button", { name: "הוספה — דנה כהן" }));
    await waitFor(() => {
      expect(onAssign).toHaveBeenCalled();
    });
    expect(screen.getByRole("status")).toHaveTextContent("");
  });
});

describe("every control obeys §2.0", () => {
  it("is size md and never gold, on every row", () => {
    mount({ assignments: [ASSIGNED], staff: [RONIT, DANA, MICHAL] });
    const buttons = screen.getAllByRole("button");
    expect(buttons.length).toBeGreaterThan(0);
    for (const button of buttons) {
      // 44px floor: `size="md"` is `min-h-11`, and `size="sm"` is forbidden in
      // this feature.
      expect(button).toHaveClass("min-h-11");
      // The dialog carries NO `primary` — a gold button per row is the same wall
      // of CTAs one modal deeper.
      expect(button).not.toHaveClass("bg-gold");
    }
  });

  it("disables only the pressed button while its write is in flight", async () => {
    let release = () => {};
    onAssign.mockImplementation(
      () =>
        new Promise<boolean>((resolve) => {
          release = () => {
            resolve(true);
          };
        }),
    );
    mount({ staff: [DANA, NOA] });
    const pressed = screen.getByRole("button", { name: "הוספה — דנה כהן" });
    const other = screen.getByRole("button", { name: "הוספה — נועה כץ" });
    fireEvent.click(pressed);
    await waitFor(() => {
      expect(pressed).toBeDisabled();
    });
    // Two rows may be written concurrently — that is legal and it is how she
    // works — so the guard is per-control, never per-dialog.
    expect(other).not.toBeDisabled();
    release();
    await waitFor(() => {
      expect(pressed).not.toBeDisabled();
    });
  });
});

describe("the write failure", () => {
  it("renders the pane's one sentence where she is looking", () => {
    mount({ error: "כבר שובצה אחראית משמרת למשמרת הזו." });
    expect(screen.getByRole("alert")).toHaveTextContent("כבר שובצה אחראית משמרת למשמרת הזו.");
  });
});
