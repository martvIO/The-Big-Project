import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Settings } from "../api";
// Side-effect import: the section renders through useTranslation, so without
// i18next initialised every assertion below would match a bare key.
import "../i18n";
import { ProfileSection } from "../components/ProfileSection";

vi.mock("../api", async () => {
  const actual = await vi.importActual<typeof import("../api")>("../api");
  return {
    errorMessage: actual.errorMessage,
    api: {
      getSettings: vi.fn(),
      updateSettings: vi.fn(),
    },
  };
});

const { api } = await import("../api");
const getSettings = vi.mocked(api.getSettings);
const updateSettings = vi.mocked(api.updateSettings);

function settings(profile: Settings["profile"] = {}): Settings {
  return { profile, toggles: { deposits_enabled: false, brides_only: false } };
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("ProfileSection public-visibility disclosure", () => {
  it("discloses under the profile heading that these fields are published", async () => {
    getSettings.mockResolvedValue(settings());
    render(<ProfileSection />);

    const notice = await screen.findByText("השדות האלה מופיעים בדף הפומבי של הבוטיק");

    // Placement is the point, and it is pinned from BOTH sides: the line must
    // sit under the profile heading and ABOVE the fields it describes, not
    // merely somewhere before the toggles. F10 is the PR that makes phone and
    // address world-readable, so a disclosure the owner scrolls past after
    // typing her home address has already failed.
    const profileHeading = screen.getByRole("heading", { name: "פרופיל הבוטיק" });
    const address = screen.getByLabelText("כתובת");
    const toggles = screen.getByText("הגדרות");

    // heading → notice → address → toggles, in that DOM order.
    expect(profileHeading.compareDocumentPosition(notice)).toBe(Node.DOCUMENT_POSITION_FOLLOWING);
    expect(notice.compareDocumentPosition(address)).toBe(Node.DOCUMENT_POSITION_FOLLOWING);
    expect(address.compareDocumentPosition(toggles)).toBe(Node.DOCUMENT_POSITION_FOLLOWING);
  });
});

describe("ProfileSection essence and instagram", () => {
  it("renders both fields from the loaded settings", async () => {
    getSettings.mockResolvedValue(
      settings({ essence: "שמלות כלה בעבודת יד", instagram: "bella.bridal" }),
    );
    render(<ProfileSection />);

    expect(await screen.findByLabelText("משפט פתיחה")).toHaveValue("שמלות כלה בעבודת יד");
    const instagram = screen.getByLabelText("אינסטגרם");
    expect(instagram).toHaveValue("bella.bridal");
    // Latin handle on an RTL page — same treatment maps_url gets.
    expect(instagram).toHaveAttribute("dir", "ltr");
    // The server rejects a leading @ outright, so the rule is stated up front.
    expect(screen.getByText("שם המשתמש בלבד, ללא @")).toBeInTheDocument();
  });

  it("submits edited essence and instagram values", async () => {
    getSettings.mockResolvedValue(settings({ phone: "03-5550100" }));
    updateSettings.mockResolvedValue(
      settings({ phone: "03-5550100", essence: "אלגנטיות שקטה", instagram: "bella.bridal" }),
    );
    render(<ProfileSection />);

    fireEvent.change(await screen.findByLabelText("משפט פתיחה"), {
      target: { value: "אלגנטיות שקטה" },
    });
    fireEvent.change(screen.getByLabelText("אינסטגרם"), { target: { value: "bella.bridal" } });
    fireEvent.click(screen.getByRole("button", { name: "שמירת פרופיל והגדרות" }));

    await waitFor(() => expect(updateSettings).toHaveBeenCalledTimes(1));
    expect(updateSettings).toHaveBeenCalledWith(
      expect.objectContaining({
        profile: expect.objectContaining({
          essence: "אלגנטיות שקטה",
          instagram: "bella.bridal",
          phone: "03-5550100",
        }),
      }),
    );
    // The saved response is what the form re-renders from.
    expect(await screen.findByLabelText("אינסטגרם")).toHaveValue("bella.bridal");
  });
});
