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
    render(<TermsSection role="owner" />);
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
    render(<TermsSection role="owner" />);
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
    render(<TermsSection role="owner" />);
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
    render(<TermsSection role="owner" />);
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
    render(<TermsSection role="owner" />);
    await screen.findByTestId("terms-setup-blocker");

    fireEvent.click(screen.getByRole("button", { name: "שמירת גרסה חדשה" }));

    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(createTermsVersion).not.toHaveBeenCalled();
  });
});

// --- F51: the publish form is owner-only (spec D9), the blocker is not (plan C4) ---

describe("TermsSection role gating", () => {
  it("hides the publish form from a shift manager", async () => {
    getTerms.mockResolvedValue(emptyHistory);
    render(<TermsSection role="shift_manager" />);
    await screen.findByTestId("terms-setup-blocker");
    // POST /manage/terms is one of the epic's two owner-only surfaces. Without
    // this she taps «שמירת גרסה חדשה» and gets the generic 403 — whose message
    // is ENGLISH and which errorMessage() surfaces verbatim into a Hebrew
    // console.
    expect(screen.queryByRole("button", { name: "שמירת גרסה חדשה" })).toBeNull();
  });

  it("keeps the setup blocker for a shift manager but swaps its action sentence", async () => {
    getTerms.mockResolvedValue(emptyHistory);
    render(<TermsSection role="shift_manager" />);
    const blocker = await screen.findByTestId("terms-setup-blocker");
    // She still has to learn that bookings cannot be accepted — hiding the
    // blocker with the form would leave the boutique silently unbookable for
    // exactly the persona standing at the desk.
    expect(blocker).toHaveTextContent("לא ניתן לקבל הזמנות ללא מדיניות ביטולים פעילה");
    expect(blocker).toHaveTextContent("יש לפנות לבעלת הבוטיק כדי להגדיר מדיניות ביטולים.");
    // The owner's sentence points at a form; hers must not.
    expect(blocker).not.toHaveTextContent("למטה");
  });

  it("keeps the owner's blocker pointing at the form below it", async () => {
    getTerms.mockResolvedValue(emptyHistory);
    render(<TermsSection role="owner" />);
    const blocker = await screen.findByTestId("terms-setup-blocker");
    expect(blocker).toHaveTextContent("יש ליצור גרסה ראשונה למטה");
    expect(screen.getByRole("button", { name: "שמירת גרסה חדשה" })).toBeInTheDocument();
  });

  it("still shows a shift manager the current policy and the history", async () => {
    getTerms.mockResolvedValue({
      current: version(2),
      versions: [version(2), version(1)],
      total: 2,
      offset: 0,
      limit: 50,
    });
    render(<TermsSection role="shift_manager" />);
    await screen.findByText("נוסח גרסה 2");
    // GET /manage/terms is NOT owner-only, so the nav item stays visible for
    // both roles while the form does not.
    expect(screen.getByText("נוסח גרסה 1")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "שמירת גרסה חדשה" })).toBeNull();
  });
});
