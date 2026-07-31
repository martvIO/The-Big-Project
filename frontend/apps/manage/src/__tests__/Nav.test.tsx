import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import "../i18n";
import type { Staff } from "../api";
import { App } from "../App";

// Every section this App mounts reaches for the API on mount; the sections
// themselves are covered by their own suites, so here they get a client whose
// reads never settle and render their loading state.
vi.mock("../api", async () => {
  const actual = await vi.importActual<typeof import("../api")>("../api");
  const pending = () => new Promise(() => {});
  return {
    ApiError: actual.ApiError,
    errorMessage: actual.errorMessage,
    api: {
      me: vi.fn(),
      login: vi.fn(),
      logout: vi.fn().mockResolvedValue({ ok: true }),
      getSettings: pending,
      getAvailability: pending,
      listAppointmentTypes: pending,
      getTerms: pending,
      listDresses: pending,
      listBookings: pending,
      listStaff: pending,
      gatewayStatus: pending,
    },
  };
});

const { api } = await import("../api");
const me = vi.mocked(api.me);
const login = vi.mocked(api.login);

function staff(role: string): Staff {
  return {
    id: "11111111-1111-1111-1111-111111111111",
    email: "sara@bella.example",
    display_name: "שרה",
    role,
  };
}

const NAV_LABELS = [
  "פרופיל והגדרות",
  "שעות פעילות",
  "סוגי תורים",
  "מדיניות ביטולים",
  "שמלות",
  "תורים",
  // The two owner-only rows, last. Everything above is `roles: ALL`, which is
  // what keeps the shift_manager assertions below a `.slice(0, 6)`.
  "צוות",
  "סליקה ותשלומים",
];

function navItems(): string[] {
  // queryAllByRole, not getAllByRole: an out-of-enum role reaches no row at all,
  // and "the nav is empty" has to be an assertion rather than a thrown query.
  return within(screen.getByRole("navigation"))
    .queryAllByRole("button")
    .map((button) => button.textContent ?? "");
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("the console nav is role-filtered", () => {
  it("shows an owner all eight sections including Staff and the gateway", async () => {
    me.mockResolvedValue(staff("owner"));
    render(<App />);
    await screen.findByRole("navigation");
    expect(navItems()).toEqual(NAV_LABELS);
  });

  it("shows a shift manager six sections and neither owner-only one", async () => {
    me.mockResolvedValue(staff("shift_manager"));
    render(<App />);
    await screen.findByRole("navigation");
    expect(navItems()).toEqual(NAV_LABELS.slice(0, 6));
    expect(screen.queryByRole("button", { name: "צוות" })).toBeNull();
    // Cosmetics only — the control is the server's owner-only RoleGate, which
    // refuses her on all four /manage/gateway routes with a 403. The filter
    // exists so she is not shown a door that answers one.
    expect(screen.queryByRole("button", { name: "סליקה ותשלומים" })).toBeNull();
  });

  it("does not white-screen on a role the enum does not know", async () => {
    // GET /manage/auth/me echoes staff_users.role verbatim with no allowlist,
    // so an out-of-enum string CAN reach this component. Every row is then
    // unreachable — the cosmetics fail closed, which is right — and the guard
    // must answer with an empty nav rather than reading `reachable[0].key` off
    // an empty array. 0011's CHECK is what makes the row impossible; a white
    // screen would be a worse failure than the impossible state.
    me.mockResolvedValue(staff("no-such-role"));
    render(<App />);
    await screen.findByRole("navigation");
    expect(navItems()).toEqual([]);
  });

  it("is cosmetics only — the server's RoleGate is what actually refuses", async () => {
    // Pinned as a test so a later "simplification" of the server gate has to
    // delete this sentence deliberately. A shift manager reaching /manage/staff
    // by any other route gets a 403, and StaffSection maps that to Hebrew.
    me.mockResolvedValue(staff("shift_manager"));
    render(<App />);
    await screen.findByRole("navigation");
    expect(navItems()).not.toContain("צוות");
  });
});

describe("an unreachable section falls back to the first reachable one", () => {
  it("does not strand a shift manager on the staff panel after a handover", async () => {
    // The real path: an owner sitting on «צוות» logs out and hands the
    // front-desk browser to a shift manager. handleLogout clears `staff` but not
    // `section`, so without the guard she would land on a dead panel.
    me.mockResolvedValue(staff("owner"));
    render(<App />);
    await screen.findByRole("navigation");

    fireEvent.click(screen.getByRole("button", { name: "צוות" }));
    expect(screen.getByRole("button", { name: "צוות" })).toHaveAttribute("aria-current", "page");

    fireEvent.click(screen.getByRole("button", { name: "יציאה" }));
    await screen.findByRole("button", { name: "כניסה" });

    login.mockResolvedValue(staff("shift_manager"));
    fireEvent.change(screen.getByLabelText("אימייל"), { target: { value: "d@b.example" } });
    fireEvent.change(screen.getByLabelText("סיסמה"), { target: { value: "pw" } });
    fireEvent.click(screen.getByRole("button", { name: "כניסה" }));

    await screen.findByRole("navigation");
    expect(navItems()).toEqual(NAV_LABELS.slice(0, 6));
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "פרופיל והגדרות" })).toHaveAttribute(
        "aria-current",
        "page",
      ),
    );
  });
});
