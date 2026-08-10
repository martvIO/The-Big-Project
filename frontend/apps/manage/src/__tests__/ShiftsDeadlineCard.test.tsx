import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import "../i18n";
import { api } from "../api";
import type { Settings } from "../api";
import { ShiftsDeadlineCard } from "../components/ShiftsDeadlineCard";

vi.mock("../api", async () => {
  const actual = await vi.importActual<typeof import("../api")>("../api");
  return {
    ...actual,
    api: { ...actual.api, getSettings: vi.fn(), updateSettings: vi.fn() },
  };
});

const getSettings = vi.mocked(api.getSettings);
const updateSettings = vi.mocked(api.updateSettings);

function settings(scheduling: Settings["scheduling"]): Settings {
  return { profile: {}, toggles: {}, scheduling };
}

const DEFAULTS = { submission_deadline_day_of_week: 3, submission_deadline_time: "18:00" };

beforeEach(() => {
  vi.clearAllMocks();
  getSettings.mockResolvedValue(settings(DEFAULTS));
  updateSettings.mockImplementation(async (body) =>
    settings(body.scheduling ?? DEFAULTS),
  );
});

describe("the deadline card", () => {
  it("prefills both fields from the wire with no `?? default` anywhere", async () => {
    // D6: the block arrives DEFAULT-COMPLETE, so every tenant carries the whole
    // pair whether or not she has ever opened this Card.
    render(<ShiftsDeadlineCard />);
    expect(await screen.findByLabelText("יום ההגשה האחרון")).toHaveValue("3");
    expect(screen.getByLabelText("שעת ההגשה")).toHaveValue("18:00");
  });

  it("sends BOTH keys in one save", async () => {
    // ⚠ THE DATA-LOSS BUG'S SHAPE. `merge_settings` merges at the top level only,
    // so a patch naming one of the two DELETES the other — which is also why
    // this Card has one save button and not two. Asserted on `Object.keys`,
    // because the shape is the defect and not the values.
    render(<ShiftsDeadlineCard />);
    fireEvent.change(await screen.findByLabelText("יום ההגשה האחרון"), {
      target: { value: "2" },
    });
    fireEvent.click(screen.getByRole("button", { name: "שמירת מועד ההגשה" }));
    await waitFor(() => {
      expect(updateSettings).toHaveBeenCalledTimes(1);
    });
    const sent = updateSettings.mock.calls[0][0].scheduling;
    expect(Object.keys(sent ?? {}).sort()).toEqual([
      "submission_deadline_day_of_week",
      "submission_deadline_time",
    ]);
    expect(sent).toEqual({ submission_deadline_day_of_week: 2, submission_deadline_time: "18:00" });
  });

  it("offers exactly one save control", async () => {
    render(<ShiftsDeadlineCard />);
    await screen.findByLabelText("שעת ההגשה");
    expect(screen.getAllByRole("button")).toHaveLength(1);
  });

  it("syncs the form from the response and shows the shipped saved cue", async () => {
    updateSettings.mockResolvedValue(
      settings({ submission_deadline_day_of_week: 5, submission_deadline_time: "12:15" }),
    );
    render(<ShiftsDeadlineCard />);
    fireEvent.click(await screen.findByRole("button", { name: "שמירת מועד ההגשה" }));
    expect(await screen.findByText("נשמר לפני רגע")).toBeInTheDocument();
    expect(screen.getByLabelText("יום ההגשה האחרון")).toHaveValue("5");
    expect(screen.getByLabelText("שעת ההגשה")).toHaveValue("12:15");
  });

  it("tells the person setting the number that it does not lock her", async () => {
    // D5, stated where the decision is made.
    render(<ShiftsDeadlineCard />);
    expect(
      await screen.findByText(/אחראית משמרת יכולה לרשום זמינות גם אחרי המועד/),
    ).toBeInTheDocument();
  });

  it("names the seven weekdays, Sunday first", async () => {
    render(<ShiftsDeadlineCard />);
    const select = await screen.findByLabelText("יום ההגשה האחרון");
    expect(Array.from(select.querySelectorAll("option")).map((o) => o.textContent)).toEqual([
      "ראשון",
      "שני",
      "שלישי",
      "רביעי",
      "חמישי",
      "שישי",
      "שבת",
    ]);
  });

  it("renders the house load-failure pair and retries on demand", async () => {
    getSettings.mockRejectedValueOnce(new Error("boom"));
    render(<ShiftsDeadlineCard />);
    expect(await screen.findByRole("alert")).toHaveTextContent("לא הצלחנו לטעון את הנתונים כרגע.");
    fireEvent.click(screen.getByRole("button", { name: "ניסיון נוסף" }));
    expect(await screen.findByLabelText("שעת ההגשה")).toHaveValue("18:00");
  });
});
