import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { TermsHistory, TermsVersion } from "../api";
import { TermsSection } from "../components/TermsSection";

vi.mock("../api", () => ({
  api: {
    getTerms: vi.fn(),
    createTermsVersion: vi.fn(),
  },
}));

const { api } = await import("../api");
const getTerms = vi.mocked(api.getTerms);
const createTermsVersion = vi.mocked(api.createTermsVersion);

const emptyHistory: TermsHistory = { current: null, versions: [], total: 0, offset: 0, limit: 50 };

function version(versionNumber: number): TermsVersion {
  return {
    id: `00000000-0000-0000-0000-00000000000${versionNumber}`,
    version: versionNumber,
    terms_text: `נוסח גרסה ${versionNumber}`,
    refundable_until_hours_before: 48,
    forfeit_percent: 100,
    created_by: "99999999-0000-0000-0000-000000000000",
    created_at: "2026-07-22T10:00:00Z",
  };
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("TermsSection setup blocker", () => {
  it("shows the no-policy-yet blocker when history is empty", async () => {
    getTerms.mockResolvedValue(emptyHistory);
    render(<TermsSection />);
    expect(await screen.findByTestId("terms-setup-blocker")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "שמירת גרסה חדשה" })).toBeInTheDocument();
  });

  it("hides the blocker once a version exists", async () => {
    getTerms.mockResolvedValue({
      current: version(2),
      versions: [version(2), version(1)],
      total: 2,
      offset: 0,
      limit: 50,
    });
    render(<TermsSection />);
    await screen.findByText("נוסח גרסה 2");
    expect(screen.queryByTestId("terms-setup-blocker")).toBeNull();
  });
});

describe("TermsSection immutable history", () => {
  it("renders history read-only — no edit or delete affordances", async () => {
    getTerms.mockResolvedValue({
      current: version(2),
      versions: [version(2), version(1)],
      total: 2,
      offset: 0,
      limit: 50,
    });
    render(<TermsSection />);
    await screen.findByText("נוסח גרסה 2");
    expect(screen.getByText("נוסח גרסה 1")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /עריכה|מחיקה|עדכון/ })).toBeNull();
    // The only mutation on offer is creating a NEW version.
    expect(screen.getByRole("button", { name: "שמירת גרסה חדשה" })).toBeInTheDocument();
  });
});

describe("TermsSection create flow", () => {
  it("always creates a new version via POST with the structured fields", async () => {
    getTerms.mockResolvedValue(emptyHistory);
    createTermsVersion.mockResolvedValue(version(1));
    render(<TermsSection />);
    await screen.findByTestId("terms-setup-blocker");

    fireEvent.change(screen.getByLabelText("תוכן מדיניות הביטולים"), {
      target: { value: "ביטול עד 48 שעות לפני התור — החזר מלא." },
    });
    fireEvent.change(screen.getByLabelText("החזר מלא עד (שעות לפני התור)"), {
      target: { value: "48" },
    });
    fireEvent.change(screen.getByLabelText("אחוז חילוט מחוץ לחלון"), {
      target: { value: "100" },
    });
    fireEvent.click(screen.getByRole("button", { name: "שמירת גרסה חדשה" }));

    await waitFor(() =>
      expect(createTermsVersion).toHaveBeenCalledWith({
        terms_text: "ביטול עד 48 שעות לפני התור — החזר מלא.",
        refundable_until_hours_before: 48,
        forfeit_percent: 100,
      }),
    );
    // The list refreshes after a save — still no in-place edits anywhere.
    await waitFor(() => expect(getTerms).toHaveBeenCalledTimes(2));
  });

  it("blocks invalid terms client-side without calling the API", async () => {
    getTerms.mockResolvedValue(emptyHistory);
    render(<TermsSection />);
    await screen.findByTestId("terms-setup-blocker");

    fireEvent.click(screen.getByRole("button", { name: "שמירת גרסה חדשה" }));

    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(createTermsVersion).not.toHaveBeenCalled();
  });
});
