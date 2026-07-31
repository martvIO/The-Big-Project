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
      // Without this every one of the nav tests below red-fails on mount with
      // `TypeError: api.getDashboard is not a function` — an error that names
      // the nav rather than the dashboard, because the console now LANDS on
      // DashboardSection.
      getDashboard: pending,
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

// Order-sensitive, compared with toEqual. «סקירה» is FIRST: it is the section
// the console lands on, for both roles (spec D10).
const NAV_LABELS = [
  "סקירה",
  "פרופיל והגדרות",
  "שעות פעילות",
  "סוגי תורים",
  "מדיניות ביטולים",
  "שמלות",
  "תורים",
  // F34, after «תורים» and before the owner-only rows. A board a shift manager
  // cannot open is not a shift manager's board (spec D5) — and inserting it
  // HERE rather than at the top is what keeps Q-5 = NO true structurally: the
  // landing section is NAV row 0 and nothing below it can displace it.
  "לוח היום",
  // The two owner-only rows, last. Everything above is `roles: ALL`, which is
  // what keeps the shift_manager assertions below a `.slice(0, 8)`.
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
  it("shows an owner all ten sections including Staff and the gateway", async () => {
    me.mockResolvedValue(staff("owner"));
    render(<App />);
    await screen.findByRole("navigation");
    expect(navItems()).toEqual(NAV_LABELS);
  });

  it("shows a shift manager eight sections and neither owner-only one", async () => {
    me.mockResolvedValue(staff("shift_manager"));
    render(<App />);
    await screen.findByRole("navigation");
    expect(navItems()).toEqual(NAV_LABELS.slice(0, 8));
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
    expect(navItems()).toEqual(NAV_LABELS.slice(0, 8));
    // reachable[0] is now the dashboard, not «פרופיל והגדרות» — the fallback
    // lands her on the console's landing section rather than a settings form.
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "סקירה" })).toHaveAttribute(
        "aria-current",
        "page",
      ),
    );
  });
});

describe("the board section is wired to its nav row", () => {
  it.each(["owner", "shift_manager"])("opens the board for a %s", async (role) => {
    // The board's own suite covers its behaviour; this is the render branch,
    // which nothing else would notice was missing.
    me.mockResolvedValue(staff(role));
    render(<App />);
    await screen.findByRole("navigation");

    fireEvent.click(screen.getByRole("button", { name: "לוח היום" }));
    expect(screen.getByRole("heading", { name: "לוח היום" })).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("טוען את לוח היום…");
  });
});

describe("the console lands on the dashboard", () => {
  it.each(["owner", "shift_manager"])(
    "puts a %s on «סקירה» on first render, with no click",
    async (role) => {
      me.mockResolvedValue(staff(role));
      render(<App />);
      await screen.findByRole("navigation");

      // First in the nav, and the initial section — the useState default and
      // the reachable[0] fallback now agree for both roles.
      expect(navItems()[0]).toBe("סקירה");
      expect(screen.getByRole("button", { name: "סקירה" })).toHaveAttribute(
        "aria-current",
        "page",
      );
    },
  );
});
