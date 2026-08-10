import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import "../i18n";
import { ApiError, api } from "../api";
import type { ShiftTemplate, ShiftWeek } from "../api";
import { MyWeekPanel } from "../components/MyWeekPanel";

vi.mock("../api", async () => {
  const actual = await vi.importActual<typeof import("../api")>("../api");
  return {
    ...actual,
    api: { ...actual.api, getShiftWeek: vi.fn(), submitAvailability: vi.fn() },
  };
});

const getShiftWeek = vi.mocked(api.getShiftWeek);
const submitAvailability = vi.mocked(api.submitAvailability);

const MORNING = "11111111-1111-1111-1111-111111111111";
const EVENING = "22222222-2222-2222-2222-222222222222";

// ⚠ 2026-11-08 IS A SUNDAY and 16:00Z is Wednesday 18:00 Jerusalem — the default
// `(3, "18:00")` deadline resolved for that week, in winter (UTC+2). The suite
// pins TZ=America/New_York, so every date read here goes through the zoned
// helpers or it renders a different day.
const WEEK_START = "2026-11-08";
const WEEK_END = "2026-11-14";
const DEADLINE = "2026-11-04T16:00:00Z";

function template(overrides: Partial<ShiftTemplate> = {}): ShiftTemplate {
  return {
    id: MORNING,
    day_of_week: 0,
    label: "משמרת בוקר",
    starts_at_time: "09:00:00",
    ends_at_time: "14:00:00",
    sort_order: 0,
    future_submission_count: null,
    // F40 D10's sparse map. `{}` is «no target», which is the default
    // state of every template that predates the feature.
    coverage_targets: {},
    ...overrides,
  };
}

function week(overrides: Partial<ShiftWeek> = {}): ShiftWeek {
  return {
    week_start: WEEK_START,
    week_end: WEEK_END,
    deadline_at: DEADLINE,
    locked: false,
    templates: [template()],
    entries: [],
    // F40 D17: not published, and therefore no shifts of her own.
    roster_published: false,
    rostered_template_ids: [],
    ...overrides,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  getShiftWeek.mockResolvedValue(week());
  submitAvailability.mockImplementation(async (body) =>
    week({
      entries: body.entries.map((entry, index) => ({
        id: `entry-${index}`,
        shift_template_id: entry.shift_template_id,
        state: entry.state,
        recorded_by_name: null,
      })),
    }),
  );
});

function mount(elevated = false) {
  return render(<MyWeekPanel elevated={elevated} />);
}

describe("the week payload", () => {
  it("asks for no week at all on first load", async () => {
    // D1: no parameter means NEXT week, resolved server-side. Sending a
    // client-computed «next» would disagree with the server for part of every
    // day on a browser in another zone.
    mount();
    await screen.findByText("משמרת בוקר · 09:00–14:00");
    expect(getShiftWeek).toHaveBeenCalledWith(undefined);
  });

  it("renders the week range and the deadline as a real day and month", async () => {
    // ⚠ THE `NaN.11` REGRESSION. `plainDayMonth(deadline_at)` splits the instant
    // on `-`, so its day part is "04T16:00:00Z" and `Number(...)` is NaN — on the
    // most-viewed line in the feature.
    mount();
    expect(await screen.findByText(/8–14/)).toBeInTheDocument();
    expect(screen.getByText("מועד ההגשה: יום רביעי, 4.11, 18:00")).toBeInTheDocument();
  });

  it("names the weekday and month of a deadline that falls on the previous UTC day", async () => {
    // ⚠ THE DST DAY-SLIP. A tenant whose deadline is «01:00» resolves Wednesday
    // 01:00 Jerusalem to 23:00Z on TUESDAY, so a hand-sliced instant would name
    // Tuesday beside a weekday that says Wednesday.
    getShiftWeek.mockResolvedValue(week({ deadline_at: "2026-11-03T23:00:00Z" }));
    mount();
    expect(await screen.findByText("מועד ההגשה: יום רביעי, 4.11, 01:00")).toBeInTheDocument();
  });

  it("heads each weekday with the right calendar date", async () => {
    // `addDays` on the plain wire date. A naive `new Date(week_start).getDate()`
    // renders «ראשון · 7.11» under TZ=America/New_York.
    getShiftWeek.mockResolvedValue(
      week({ templates: [template(), template({ id: EVENING, day_of_week: 4 })] }),
    );
    mount();
    expect(await screen.findByRole("heading", { name: "ראשון · 8.11" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "חמישי · 12.11" })).toBeInTheDocument();
  });

  it("renders no weekday section for a day with no template", async () => {
    // A Saturday heading over nothing is chrome that says «you are missing
    // something» — and Saturday having no shifts is the tenant's own data (D3),
    // never a hardcoded Shabbat rule.
    mount();
    expect(screen.queryByRole("heading", { name: /שבת/ })).not.toBeInTheDocument();
  });
});

describe("the save payload", () => {
  it("omits every shift still sitting on «לא נרשם» and sends the rest", async () => {
    // D11's whole-week replace plus D8's clear path: an omitted template has its
    // live row soft-deleted server-side.
    getShiftWeek.mockResolvedValue(
      week({ templates: [template(), template({ id: EVENING, label: "משמרת ערב" })] }),
    );
    mount();
    const groups = await screen.findAllByRole("group");
    fireEvent.click(within(groups[0]).getByRole("radio", { name: "מעדיפה" }));
    fireEvent.click(screen.getByRole("button", { name: "שמירת זמינות" }));

    await waitFor(() => {
      expect(submitAvailability).toHaveBeenCalledWith({
        week_start: WEEK_START,
        entries: [{ shift_template_id: MORNING, state: "preferred" }],
      });
    });
  });

  it("sends an empty list when she clears her whole week", async () => {
    getShiftWeek.mockResolvedValue(
      week({
        entries: [
          {
            id: "e1",
            shift_template_id: MORNING,
            state: "available",
            recorded_by_name: null,
          },
        ],
      }),
    );
    mount();
    const group = await screen.findByRole("group");
    fireEvent.click(within(group).getByRole("radio", { name: "לא נרשם" }));
    fireEvent.click(screen.getByRole("button", { name: "שמירת זמינות" }));
    await waitFor(() => {
      expect(submitAvailability).toHaveBeenCalledWith({ week_start: WEEK_START, entries: [] });
    });
  });

  it("shows the shipped saved cue rather than minting one", async () => {
    mount();
    fireEvent.click(await screen.findByRole("button", { name: "שמירת זמינות" }));
    expect(await screen.findByText("נשמר לפני רגע")).toBeInTheDocument();
  });
});

describe("«סימון כל השאר כזמינה»", () => {
  it("fills only the unanswered shifts and never overwrites an answer", async () => {
    // ⚠ NON-DESTRUCTIVE BY CONSTRUCTION, which is what removes any need for an
    // undo. This is the single control that cuts her path from 14 taps to ~4.
    getShiftWeek.mockResolvedValue(
      week({
        templates: [template(), template({ id: EVENING, label: "משמרת ערב" })],
        entries: [
          {
            id: "e1",
            shift_template_id: MORNING,
            state: "unavailable",
            recorded_by_name: null,
          },
        ],
      }),
    );
    mount();
    fireEvent.click(await screen.findByRole("button", { name: "סימון כל השאר כזמינה" }));
    const groups = screen.getAllByRole("group");
    expect(within(groups[0]).getByRole("radio", { name: "לא זמינה" })).toBeChecked();
    expect(within(groups[1]).getByRole("radio", { name: "זמינה" })).toBeChecked();
  });

  it("announces its result through the progress line's live region", async () => {
    // ⚠ WITHOUT THIS, THE ONE CONTROL THAT CUTS 14 TAPS TO 4 IS THE ONE CONTROL A
    // BLIND STAFFER CANNOT VERIFY: it mutates up to twelve groups, its own name
    // does not change, and the groups are below it. No new copy key — a second
    // sentence about a number the first already carries could drift from it.
    getShiftWeek.mockResolvedValue(
      week({ templates: [template(), template({ id: EVENING, label: "משמרת ערב" })] }),
    );
    mount();
    const progress = await screen.findByText("נענו: 0 מתוך 2");
    expect(progress).toHaveAttribute("role", "status");
    fireEvent.click(screen.getByRole("button", { name: "סימון כל השאר כזמינה" }));
    expect(screen.getByText("נענו: 2 מתוך 2")).toHaveAttribute("role", "status");
  });
});

describe("the locked week", () => {
  it("shows a <dl> of her answers, no save button and no disabled radio", async () => {
    // ⚠ A DISABLED CONTROL IS NOT FOCUSABLE, so disabled radios would strand a
    // keyboard or screen-reader user from the answers she already gave — the one
    // thing the locked screen exists to show her. And the save button is REMOVED
    // rather than disabled: a disabled save on a locked form promises an act it
    // cannot perform.
    getShiftWeek.mockResolvedValue(
      week({
        locked: true,
        entries: [
          {
            id: "e1",
            shift_template_id: MORNING,
            state: "preferred",
            recorded_by_name: null,
          },
        ],
      }),
    );
    mount();
    expect(await screen.findByText(/מועד ההגשה לשבוע הזה עבר/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "שמירת זמינות" })).not.toBeInTheDocument();
    expect(screen.queryAllByRole("radio")).toHaveLength(0);
    expect(screen.getByText("מעדיפה")).toBeInTheDocument();
    expect(screen.getByText(/09:00–14:00/)).toBeInTheDocument();
  });

  it("names «לא נרשם» in the locked list for a shift she never answered", async () => {
    getShiftWeek.mockResolvedValue(week({ locked: true }));
    mount();
    expect(await screen.findByText("לא נרשם")).toBeInTheDocument();
  });

  it("keeps the save button for an elevated actor and swaps the banner for a note", async () => {
    // ⚠ D5 / design F-1. An elevated actor is not subject to the deadline at
    // all, so a `locked` computed without an actor would remove the owner's save
    // button on a write that would have succeeded. She must still be TOLD she is
    // acting past it — `after_deadline: true` is going into her audit row.
    getShiftWeek.mockResolvedValue(week({ locked: false }));
    mount(true);
    expect(await screen.findByRole("button", { name: "שמירת זמינות" })).toBeInTheDocument();

    getShiftWeek.mockResolvedValue(week({ locked: true }));
    const { rerender } = render(<MyWeekPanel elevated />);
    rerender(<MyWeekPanel elevated />);
    expect(await screen.findByText("מועד ההגשה עבר. הרישום שלך עדיין אפשרי.")).toBeInTheDocument();
  });
});

describe("failures", () => {
  it("renders the house load-failure pair and retries on demand", async () => {
    getShiftWeek.mockRejectedValueOnce(new Error("boom"));
    mount();
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "לא הצלחנו לטעון את הנתונים כרגע.",
    );
    fireEvent.click(screen.getByRole("button", { name: "ניסיון נוסף" }));
    expect(await screen.findByText("משמרת בוקר · 09:00–14:00")).toBeInTheDocument();
  });

  it("maps each of the four codes to its own Hebrew sentence", async () => {
    for (const [code, hebrew] of [
      ["SUBMISSION_CLOSED", "מועד ההגשה לשבוע הזה עבר."],
      ["WEEK_OUT_OF_RANGE", "אפשר להגיש רק לשבועות הקרובים."],
      ["NOT_AUTHORIZED", "אין הרשאה לרשום זמינות עבור אשת צוות אחרת כרגע. לבירור אפשר לפנות לבעלת הבוטיק."],
      ["NOT_FOUND", "המשמרת או אשת הצוות כבר לא זמינות. הרשימה תתוקן בעדכון הבא."],
    ] as const) {
      vi.clearAllMocks();
      getShiftWeek.mockResolvedValue(week());
      submitAvailability.mockRejectedValue(new ApiError(409, code, "english"));
      const view = render(<MyWeekPanel elevated={false} />);
      fireEvent.click(await view.findByRole("button", { name: "שמירת זמינות" }));
      expect(await view.findByText(hebrew)).toBeInTheDocument();
      view.unmount();
    }
  });

  it("falls through to the server's own text for an UNMAPPED code, visibly", async () => {
    // ⚠ DELIBERATE. `MAPPED_CODES` is a hand-kept map that nothing pins, so a
    // sixth code renders English on a green build — and a visible English
    // sentence is a better failure than a silently wrong Hebrew one.
    submitAvailability.mockRejectedValue(new ApiError(409, "SOMETHING_NEW", "a new refusal"));
    mount();
    fireEvent.click(await screen.findByRole("button", { name: "שמירת זמינות" }));
    expect(await screen.findByText("a new refusal")).toBeInTheDocument();
  });

  it("flips to the locked render and moves focus when a save is refused as closed", async () => {
    // ⚠ THE SAVE BUTTON SHE JUST PRESSED IS GONE, so focus falls to <body> and
    // her next Tab restarts at the skip link — after twelve answered shifts,
    // that is a traverse of the shell and the whole nav (WCAG 2.4.3).
    submitAvailability.mockRejectedValue(new ApiError(409, "SUBMISSION_CLOSED", "closed"));
    getShiftWeek.mockResolvedValueOnce(week()).mockResolvedValue(week({ locked: true }));
    mount();
    fireEvent.click(await screen.findByRole("button", { name: "שמירת זמינות" }));

    const banner = await screen.findByText(/מועד ההגשה לשבוע הזה עבר\. אפשר לפנות/);
    expect(screen.queryByRole("button", { name: "שמירת זמינות" })).not.toBeInTheDocument();
    await waitFor(() => {
      expect(banner).toHaveFocus();
    });
  });
});

describe("week navigation", () => {
  it("uses words rather than chevrons and walks a whole week", async () => {
    // DL20: this console ships no icon-only control, and an `aria-label` on a
    // glyph is a name no sighted user can verify. A second benefit falls out for
    // free — there is no directional glyph to get backwards in RTL.
    mount();
    fireEvent.click(await screen.findByRole("button", { name: "השבוע הבא" }));
    await waitFor(() => {
      expect(getShiftWeek).toHaveBeenLastCalledWith("2026-11-15");
    });
    fireEvent.click(screen.getByRole("button", { name: "השבוע הקודם" }));
    await waitFor(() => {
      expect(getShiftWeek).toHaveBeenLastCalledWith("2026-11-08");
    });
  });

  it("disables the forward button three weeks past the server's default", async () => {
    // The server's default is NEXT week, so D1's ±4 around the CURRENT week is
    // [-5, +3] around this origin. The panel never computes «next week» itself.
    mount();
    const forward = await screen.findByRole("button", { name: "השבוע הבא" });
    for (let step = 0; step < 3; step += 1) {
      fireEvent.click(screen.getByRole("button", { name: "השבוע הבא" }));
      await waitFor(() => {
        expect(getShiftWeek).toHaveBeenCalled();
      });
    }
    await waitFor(() => {
      expect(forward).toBeDisabled();
    });
  });
});

describe("attribution", () => {
  it("names the colleague who recorded an answer in her name", async () => {
    getShiftWeek.mockResolvedValue(
      week({
        entries: [
          {
            id: "e1",
            shift_template_id: MORNING,
            state: "available",
            recorded_by_name: "דנה כהן",
          },
        ],
      }),
    );
    mount();
    // The line is split across elements by <Trans>'s <bdi> island, so it is
    // read off the group's own description rather than by text match.
    const group = await screen.findByRole("group");
    const describedBy = group.getAttribute("aria-describedby");
    expect(document.getElementById(describedBy as string)?.textContent).toBe(
      "נרשם על ידי דנה כהן.",
    );
  });
});

describe("the empty week", () => {
  it("states the absence as a fact rather than her fault, with no seed button", async () => {
    // The seed lives in ShiftTemplatesPane and has exactly one owner; offering
    // it here would be a door that 403s.
    getShiftWeek.mockResolvedValue(week({ templates: [] }));
    mount();
    expect(await screen.findByText("עדיין לא הוגדרו משמרות לשבוע הזה.")).toBeInTheDocument();
    expect(
      screen.getByText("כשאחראית המשמרת תגדיר משמרות, אפשר יהיה לסמן כאן זמינות."),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "יצירת משמרות משעות הפעילות" }),
    ).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "שמירת זמינות" })).not.toBeInTheDocument();
  });
});

describe("F40 D17: her published shifts", () => {
  it("says the roster is not published yet, and never the other two sentences", async () => {
    // ⚠ THREE DISTINCT FACTS, THREE DISTINCT SENTENCES (D5). A draft answers
    // this one EVEN WITH HER ON IT — a draft is invisible to staff (D6), and
    // telling her «you work Sunday morning» off an unpublished week is exactly
    // the promise this feature must not make.
    getShiftWeek.mockResolvedValue(week({ roster_published: false, rostered_template_ids: [] }));
    mount();
    expect(await screen.findByText("סידור העבודה לשבוע הזה טרם פורסם.")).toBeInTheDocument();
    expect(screen.queryByText("לא שובצת למשמרות בשבוע הזה.")).toBeNull();
  });

  it("says she is on nothing when the week IS published and her list is empty", async () => {
    getShiftWeek.mockResolvedValue(week({ roster_published: true, rostered_template_ids: [] }));
    mount();
    expect(await screen.findByText("לא שובצת למשמרות בשבוע הזה.")).toBeInTheDocument();
    expect(screen.queryByText("סידור העבודה לשבוע הזה טרם פורסם.")).toBeNull();
  });

  it("lists only her shifts, in the server's order", async () => {
    getShiftWeek.mockResolvedValue(
      week({
        templates: [template(), template({ id: EVENING, label: "משמרת ערב" })],
        roster_published: true,
        rostered_template_ids: [EVENING],
      }),
    );
    mount();
    const heading = await screen.findByRole("heading", { name: "המשמרות שלי" });
    const block = heading.parentElement as HTMLElement;
    const rows = within(block).getAllByRole("listitem");
    expect(rows).toHaveLength(1);
    expect(rows[0].textContent).toContain("משמרת ערב");
    expect(within(block).queryByText(/משמרת בוקר/)).toBeNull();
  });

  it("carries NO control and NO total of any kind", async () => {
    // ⚠ §0.3, on the surface most tempting to add one to. This is not an
    // hours-worked record: no «סה"כ שעות», no weekly sum, no count of shifts —
    // and no button, because a staffer accepting a shift is the attendance punch
    // D13 and the epic's labour-law row put out of scope.
    getShiftWeek.mockResolvedValue(
      week({ roster_published: true, rostered_template_ids: [MORNING] }),
    );
    mount();
    const heading = await screen.findByRole("heading", { name: "המשמרות שלי" });
    const block = heading.parentElement as HTMLElement;
    expect(within(block).queryAllByRole("button")).toEqual([]);
    expect(within(block).queryAllByRole("link")).toEqual([]);
    expect(within(block).queryAllByRole("textbox")).toEqual([]);
    expect(within(block).queryAllByRole("radio")).toEqual([]);
    expect(block.textContent).not.toContain('סה"כ');
  });

  it("leaves the shipped radios, the deadline line and the save button untouched", async () => {
    // The block is ADDITIVE. F39's whole panel must keep working, which is why
    // its own tests above are unedited.
    getShiftWeek.mockResolvedValue(
      week({ roster_published: true, rostered_template_ids: [MORNING] }),
    );
    mount();
    expect(await screen.findAllByRole("group")).not.toHaveLength(0);
    expect(screen.getByRole("button", { name: "שמירת זמינות" })).toBeInTheDocument();
    expect(screen.getByText(/מועד ההגשה/)).toBeInTheDocument();
  });

  it("puts the block's h3 between the pane h2 and the weekday h3s", async () => {
    // Heading levels: Card h2 -> this h3 -> the form's weekday h3s. Same level,
    // two siblings, nothing skipped (design §10).
    getShiftWeek.mockResolvedValue(
      week({ roster_published: true, rostered_template_ids: [MORNING] }),
    );
    mount();
    await screen.findByRole("heading", { name: "המשמרות שלי" });
    const levels = screen
      .getAllByRole("heading")
      .map((node) => Number(node.tagName.slice(1)));
    expect(levels[0]).toBe(2);
    expect(levels[1]).toBe(3);
    expect(Math.max(...levels)).toBe(3);
  });
});
