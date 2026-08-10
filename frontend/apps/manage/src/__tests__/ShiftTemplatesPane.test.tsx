import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import "../i18n";
import { ApiError, api } from "../api";
import type { ShiftTemplate } from "../api";
import { ShiftTemplatesPane } from "../components/ShiftTemplatesPane";
import { MAX_TEMPLATES_PER_DAY } from "../validation";

vi.mock("../api", async () => {
  const actual = await vi.importActual<typeof import("../api")>("../api");
  return {
    ...actual,
    api: {
      ...actual.api,
      listShiftTemplates: vi.fn(),
      createShiftTemplate: vi.fn(),
      updateShiftTemplate: vi.fn(),
      deleteShiftTemplate: vi.fn(),
      seedShiftTemplates: vi.fn(),
      getAvailability: vi.fn(),
    },
  };
});

const listShiftTemplates = vi.mocked(api.listShiftTemplates);
const updateShiftTemplate = vi.mocked(api.updateShiftTemplate);
const deleteShiftTemplate = vi.mocked(api.deleteShiftTemplate);
const seedShiftTemplates = vi.mocked(api.seedShiftTemplates);
const getAvailability = vi.mocked(api.getAvailability);

const MORNING = "11111111-1111-1111-1111-111111111111";

function template(overrides: Partial<ShiftTemplate> = {}): ShiftTemplate {
  return {
    id: MORNING,
    day_of_week: 4,
    label: "משמרת בוקר",
    starts_at_time: "09:00:00",
    ends_at_time: "14:00:00",
    sort_order: 0,
    future_submission_count: 0,
    ...overrides,
  };
}

// ⚠ THE PANE RENDERS BOTH CONFIRM DIALOGS ALWAYS, `Modal`'s shipped shape —
// `open` is a prop, not a mount. jsdom's `showModal` stub (setup.ts) only sets
// `.open`, so a closed dialog's CONTENT is still in the document and
// `queryByText` on it would pass for the wrong reason. The open one is the
// assertion.
function openDialog(): HTMLElement | undefined {
  return screen
    .queryAllByRole("dialog", { hidden: true })
    .find((node) => (node as HTMLDialogElement).open);
}

// ⚠ THIS PANE OWNS THE SECTION'S TEMPLATES READ and reports every resolved list
// upward — `ShiftsSection` observes it instead of fetching a second copy.
const onTemplates = vi.fn();

const mount = () => render(<ShiftTemplatesPane onTemplates={onTemplates} />);

beforeEach(() => {
  vi.clearAllMocks();
  listShiftTemplates.mockResolvedValue({ templates: [template()] });
  updateShiftTemplate.mockResolvedValue({ template: template(), invalidated_submissions: 0 });
  deleteShiftTemplate.mockResolvedValue({ template: null, invalidated_submissions: 0 });
  seedShiftTemplates.mockResolvedValue({ created: 3, templates: [template()] });
});

describe("the seed", () => {
  it("offers it as the whole screen when no template exists anywhere", async () => {
    listShiftTemplates.mockResolvedValue({ templates: [] });
    mount();
    expect(
      await screen.findByRole("button", { name: "יצירת משמרות משעות הפעילות" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText("המשמרות נוצרות פעם אחת משעות הפעילות, ואפשר לפצל ולשנות אותן אחר כך."),
    ).toBeInTheDocument();
  });

  it("renders the button with NO prior read of the opening hours", async () => {
    // ⚠ THE PRE-CHECK IS THE DEFECT, not the missing guard. Gating the button on
    // a `GET /manage/availability` puts a second reader of `availability_rules`
    // one request ahead of the writer, purely to hide a control the server
    // already guards. She learns the same fact one request later, from the only
    // component that actually knows.
    listShiftTemplates.mockResolvedValue({ templates: [] });
    seedShiftTemplates.mockRejectedValue(new ApiError(409, "NO_OPENING_HOURS", "english"));
    mount();
    fireEvent.click(await screen.findByRole("button", { name: "יצירת משמרות משעות הפעילות" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "לא הוגדרו שעות פעילות. אפשר להגדיר אותן במסך שעות פעילות.",
    );
    expect(getAvailability).not.toHaveBeenCalled();
  });

  it("announces the count and lands focus on that line", async () => {
    // Success unmounts the EmptyState holding the button she pressed, so focus
    // falls to <body> under the largest re-render in the feature.
    listShiftTemplates.mockResolvedValue({ templates: [] });
    mount();
    fireEvent.click(await screen.findByRole("button", { name: "יצירת משמרות משעות הפעילות" }));
    const line = await screen.findByText("משמרות שנוצרו משעות הפעילות: 3");
    expect(line).toHaveAttribute("role", "status");
    await waitFor(() => {
      expect(line).toHaveFocus();
    });
  });

  it("shows the winner's templates rather than an error over a blank list", async () => {
    // Two managers seeding at once is the only way to reach this code.
    listShiftTemplates
      .mockResolvedValueOnce({ templates: [] })
      .mockResolvedValue({ templates: [template({ label: "של השנייה" })] });
    seedShiftTemplates.mockRejectedValue(
      new ApiError(409, "TEMPLATES_ALREADY_SEEDED", "english"),
    );
    mount();
    fireEvent.click(await screen.findByRole("button", { name: "יצירת משמרות משעות הפעילות" }));
    expect(await screen.findByText("כבר קיימות משמרות. אפשר לערוך אותן ידנית.")).toBeInTheDocument();
    expect(await screen.findByText("של השנייה")).toBeInTheDocument();
  });
});

describe("the seven weekday groups", () => {
  it("renders Saturday, empty, with its own add button", async () => {
    // D3: it has no opening-hours row for almost every boutique, so the seed
    // makes no template for it — and hiding the day would make that absence look
    // like a bug rather than the tenant's own data.
    mount();
    expect(await screen.findByRole("heading", { name: "שבת" })).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: "הוספת משמרת" })).toHaveLength(7);
  });

  it("disables the add button at the per-day cap AND renders the reason as text", async () => {
    // ⚠ A DISABLED CONTROL WHOSE REASON LIVES ONLY IN A `title` IS UNREACHABLE by
    // keyboard and by AT.
    listShiftTemplates.mockResolvedValue({
      templates: Array.from({ length: MAX_TEMPLATES_PER_DAY }, (_, index) =>
        template({ id: `t-${index}`, label: `משמרת ${index}` }),
      ),
    });
    mount();
    const thursday = (await screen.findByRole("heading", { name: "חמישי" })).closest(
      "section",
    ) as HTMLElement;
    expect(within(thursday).getByRole("button", { name: "הוספת משמרת" })).toBeDisabled();
    expect(within(thursday).getByText("מספר המשמרות המרבי ליום: 6")).toBeInTheDocument();
    // A different weekday is unaffected — the cap is per day.
    const sunday = (screen.getByRole("heading", { name: "ראשון" }) as HTMLElement).closest(
      "section",
    ) as HTMLElement;
    expect(within(sunday).getByRole("button", { name: "הוספת משמרת" })).toBeEnabled();
  });
});

describe("the edit", () => {
  it("sends all five fields on the PATCH", async () => {
    // D2's full replace: an omitted key can never silently clear a value, and
    // `sort_order` is resent from the row because the console never shows it.
    mount();
    fireEvent.click(await screen.findByRole("button", { name: "עריכה" }));
    fireEvent.change(screen.getByLabelText("שם המשמרת"), { target: { value: "בוקר" } });
    fireEvent.click(screen.getByRole("button", { name: "שמירת המשמרת" }));
    await waitFor(() => {
      expect(updateShiftTemplate).toHaveBeenCalledWith(MORNING, {
        day_of_week: 4,
        label: "בוקר",
        starts_at_time: "09:00:00",
        ends_at_time: "14:00:00",
        sort_order: 0,
      });
    });
  });

  it("opens NO confirm for a label-only edit, even with answers on the row", async () => {
    // D4: renaming «משמרת בוקר» to «בוקר» changes nothing anybody answered, so
    // invalidating on it would make the owner's typo fix cost other people's
    // answers.
    listShiftTemplates.mockResolvedValue({
      templates: [template({ future_submission_count: 4 })],
    });
    mount();
    fireEvent.click(await screen.findByRole("button", { name: "עריכה" }));
    fireEvent.change(screen.getByLabelText("שם המשמרת"), { target: { value: "בוקר" } });
    fireEvent.click(screen.getByRole("button", { name: "שמירת המשמרת" }));
    await waitFor(() => {
      expect(updateShiftTemplate).toHaveBeenCalled();
    });
    expect(openDialog()).toBeUndefined();
  });

  it("states the count BEFORE she commits a material edit", async () => {
    // D4's binding sentence, and `future_submission_count` on the templates read
    // is the only route that can answer it.
    listShiftTemplates.mockResolvedValue({
      templates: [template({ future_submission_count: 4 })],
    });
    mount();
    fireEvent.click(await screen.findByRole("button", { name: "עריכה" }));
    fireEvent.change(screen.getByLabelText("שעת סיום"), { target: { value: "21:00" } });
    fireEvent.click(screen.getByRole("button", { name: "שמירת המשמרת" }));
    const dialog = await waitFor(() => {
      const found = openDialog();
      expect(found).toBeDefined();
      return found as HTMLElement;
    });
    expect(
      within(dialog).getByText(
        "שינוי המשמרת ימחק תשובות שכבר נרשמו לשבועות הבאים. תשובות שיימחקו: 4",
      ),
    ).toBeInTheDocument();
    expect(updateShiftTemplate).not.toHaveBeenCalled();
  });

  it("suppresses the confirm entirely when nothing would be lost", async () => {
    // «will delete 0 answers» is noise on the overwhelmingly common case.
    mount();
    fireEvent.click(await screen.findByRole("button", { name: "עריכה" }));
    fireEvent.change(screen.getByLabelText("שעת סיום"), { target: { value: "21:00" } });
    fireEvent.click(screen.getByRole("button", { name: "שמירת המשמרת" }));
    await waitFor(() => {
      expect(updateShiftTemplate).toHaveBeenCalled();
    });
    expect(openDialog()).toBeUndefined();
  });

  it("announces the count the response RETURNED, not the one it predicted", async () => {
    // Somebody may have submitted between the read and the write.
    updateShiftTemplate.mockResolvedValue({ template: template(), invalidated_submissions: 5 });
    mount();
    fireEvent.click(await screen.findByRole("button", { name: "עריכה" }));
    fireEvent.change(screen.getByLabelText("שעת סיום"), { target: { value: "21:00" } });
    fireEvent.click(screen.getByRole("button", { name: "שמירת המשמרת" }));
    expect(await screen.findByText("תשובות שנמחקו לשבועות הבאים: 5")).toBeInTheDocument();
  });

  it("refuses an overnight shift in Hebrew before any request", async () => {
    mount();
    fireEvent.click(await screen.findByRole("button", { name: "עריכה" }));
    fireEvent.change(screen.getByLabelText("שעת התחלה"), { target: { value: "22:00" } });
    fireEvent.change(screen.getByLabelText("שעת סיום"), { target: { value: "02:00" } });
    fireEvent.click(screen.getByRole("button", { name: "שמירת המשמרת" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "שעת הסיום חייבת להיות אחרי שעת ההתחלה.",
    );
    expect(updateShiftTemplate).not.toHaveBeenCalled();
  });
});

describe("the remove", () => {
  it("puts the removal behind a danger confirm carrying the count", async () => {
    listShiftTemplates.mockResolvedValue({
      templates: [template({ future_submission_count: 2 })],
    });
    mount();
    fireEvent.click(await screen.findByRole("button", { name: "הסרה" }));
    const dialog = await waitFor(() => {
      const found = openDialog();
      expect(found).toBeDefined();
      return found as HTMLElement;
    });
    expect(within(dialog).getByText("המשמרת לא תופיע יותר בשבועות הבאים.")).toBeInTheDocument();
    expect(within(dialog).getByText(/תשובות שיימחקו: 2/)).toBeInTheDocument();
    expect(deleteShiftTemplate).not.toHaveBeenCalled();
  });

  it("deletes on confirm", async () => {
    // ⚠ FOCUS AND DIALOG BEHAVIOUR ARE NOT ASSERTED HERE. jsdom has no
    // <dialog>: `setup.ts` stubs `showModal()`, so a focus assertion that
    // pre-places focus on its own target is vacuous. This asserts CONTENT and
    // the request; the e2e leg asserts where focus lands.
    mount();
    fireEvent.click(await screen.findByRole("button", { name: "הסרה" }));
    const dialog = await waitFor(() => {
      const found = openDialog();
      expect(found).toBeDefined();
      return found as HTMLElement;
    });
    fireEvent.click(within(dialog).getByRole("button", { name: "הסרה" }));
    await waitFor(() => {
      expect(deleteShiftTemplate).toHaveBeenCalledWith(MORNING);
    });
  });
});

describe("the read", () => {
  it("renders the house load-failure pair and retries on demand", async () => {
    listShiftTemplates.mockRejectedValueOnce(new Error("boom"));
    mount();
    expect(await screen.findByRole("alert")).toHaveTextContent("לא הצלחנו לטעון את הנתונים כרגע.");
    fireEvent.click(screen.getByRole("button", { name: "ניסיון נוסף" }));
    expect(await screen.findByText("משמרת בוקר")).toBeInTheDocument();
  });
});

describe("reporting the list upward", () => {
  it("reports every resolved list, and reports nothing when the read fails", async () => {
    // ⚠ THE CONTAINER'S §1.1 COLLAPSE KEYS ON THIS. A failed read must report
    // nothing at all: reporting `[]` would collapse an elevated actor to the
    // first-run screen on a 500, telling her the boutique has no shifts when the
    // truth is that we could not ask.
    listShiftTemplates.mockRejectedValueOnce(new Error("boom"));
    mount();
    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(onTemplates).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: "ניסיון נוסף" }));
    await waitFor(() => {
      expect(onTemplates).toHaveBeenLastCalledWith([template()]);
    });
  });

  it("reports the seeded list, which is what releases the other three panes", async () => {
    // §5.2: «the other three panes mount for the first time (§1.1's `if`
    // releases)». They can only do that if the seed's own list reaches the
    // container — a container that fetched its own copy never heard about it.
    listShiftTemplates.mockResolvedValue({ templates: [] });
    mount();
    fireEvent.click(await screen.findByRole("button", { name: "יצירת משמרות משעות הפעילות" }));
    await waitFor(() => {
      expect(onTemplates).toHaveBeenLastCalledWith([template()]);
    });
  });
});
