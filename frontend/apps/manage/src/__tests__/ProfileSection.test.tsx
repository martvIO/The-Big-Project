import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
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

const SAVE_BUTTON = "שמירת פרופיל";

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
    // F27 D7: «הגדרות» is gone with its renderer — the matrix's own «הפעלת
    // תכונות» heading is the element this ordering now pins. The CLAIM is
    // unchanged (the disclosure sits above the fields and before the switches);
    // only the element that terminates the walk moved.
    const toggles = screen.getByRole("heading", { name: "הפעלת תכונות" });

    // heading → notice → address → toggles, in that DOM order.
    expect(profileHeading.compareDocumentPosition(notice)).toBe(Node.DOCUMENT_POSITION_FOLLOWING);
    expect(notice.compareDocumentPosition(address)).toBe(Node.DOCUMENT_POSITION_FOLLOWING);
    expect(address.compareDocumentPosition(toggles)).toBe(Node.DOCUMENT_POSITION_FOLLOWING);
  });
});

// --- F27 D7: the section sheds its inline switches ---------------------------
//
// ⚠ THESE ASSERTIONS CHANGE DELIBERATELY, AND THE SPEC NAMES THAT TRAP. F7's
// tests pinned toggles-in-the-form; F27 moves them into their own card with a
// per-row save. The backend D2/D3 tests are the ones that must not weaken —
// these are the ones that must.

describe("ProfileSection after the matrix landed", () => {
  it("renders NO switch of its own — the matrix card owns every one", async () => {
    getSettings.mockResolvedValue(settings());
    render(<ProfileSection />);
    await screen.findByLabelText("כתובת");

    // The two shipped inline Toggles are gone from the FORM. The switches the
    // matrix renders live in its own card, below the form, and are asserted
    // in TogglesMatrix.test.tsx.
    const form = screen.getByRole("button", { name: SAVE_BUTTON }).closest("form");
    expect(form).not.toBeNull();
    expect(within(form as HTMLElement).queryAllByRole("switch")).toEqual([]);
  });

  it("mounts the matrix card under the profile form", async () => {
    getSettings.mockResolvedValue(settings());
    render(<ProfileSection />);

    expect(await screen.findByRole("heading", { name: "הפעלת תכונות" })).toBeInTheDocument();
    // Fed from the parent's existing fetch — no second GET (design §2).
    expect(getSettings).toHaveBeenCalledTimes(1);
  });

  it("sends a PROFILE-ONLY save payload — no toggles key at all", async () => {
    getSettings.mockResolvedValue(settings({ phone: "03-5550100" }));
    updateSettings.mockResolvedValue(settings({ phone: "03-5550100" }));
    render(<ProfileSection />);

    fireEvent.click(await screen.findByRole("button", { name: SAVE_BUTTON }));

    await waitFor(() => expect(updateSettings).toHaveBeenCalledTimes(1));
    const payload = updateSettings.mock.calls[0][0];
    expect(payload).not.toHaveProperty("toggles");
    expect(Object.keys(payload)).toEqual(["profile"]);
  });

  it("labels the save button «שמירת פרופיל» — «והגדרות» is no longer true of it", async () => {
    getSettings.mockResolvedValue(settings());
    render(<ProfileSection />);

    expect(await screen.findByRole("button", { name: SAVE_BUTTON })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "שמירת פרופיל והגדרות" })).not.toBeInTheDocument();
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
    fireEvent.click(screen.getByRole("button", { name: SAVE_BUTTON }));

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
