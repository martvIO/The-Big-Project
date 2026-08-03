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
      // Defensive, and — unlike getDashboard above — it currently pins nothing:
      // removing it reddens no test. CustomersSection puts its whole fetch
      // inside a 300ms setTimeout and clears it on unmount, so within a nav test
      // the call never lands. Kept anyway because the day that debounce moves,
      // the failure is `TypeError: api.listCustomers is not a function` on every
      // customers test — an error named after the nav rather than the section.
      // Verified by mutation rather than assumed: this line was deleted and the
      // suite stayed green.
      listCustomers: pending,
      listStaff: pending,
      // Without this every one of the nav tests below red-fails on mount with
      // `TypeError: api.getDashboard is not a function` — an error that names
      // the nav rather than the dashboard, because the console now LANDS on
      // DashboardSection.
      getDashboard: pending,
      // Same reason, one feature later: the three floor roles LAND on the floor
      // section, so <App/> mounts FloorPanel, which calls api.getFloor(). Without
      // this row every case below red-fails naming the nav rather than the floor
      // — the exact trap the comment above documents.
      getFloor: pending,
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
  // F53, immediately after «תורים»: a customer card is what a row in that list
  // leads to, and reading them next to each other is how the front desk uses
  // both. `roles: ALL` — the server's RoleGate admits a shift manager on every
  // /manage/customers route, so hiding the door would be a lie about the API.
  "לקוחות",
  // F34, after «תורים» and before the owner-only rows. A board a shift manager
  // cannot open is not a shift manager's board (spec D5) — and inserting it
  // HERE rather than at the top is what keeps Q-5 = NO true structurally: the
  // landing section is NAV row 0 and nothing below it can displace it.
  "לוח היום",
  // The two owner-only rows, last. Everything above is `roles: ALL`, which is
  // what keeps the shift_manager assertions below a `.slice(0, 9)`.
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
  it("shows an owner all eleven sections including Staff and the gateway", async () => {
    me.mockResolvedValue(staff("owner"));
    render(<App />);
    await screen.findByRole("navigation");
    expect(navItems()).toEqual(NAV_LABELS);
  });

  it("shows a shift manager nine sections and neither owner-only one", async () => {
    me.mockResolvedValue(staff("shift_manager"));
    render(<App />);
    await screen.findByRole("navigation");
    expect(navItems()).toEqual(NAV_LABELS.slice(0, 9));
    expect(screen.queryByRole("button", { name: "צוות" })).toBeNull();
    // Cosmetics only — the control is the server's owner-only RoleGate, which
    // refuses her on all four /manage/gateway routes with a 403. The filter
    // exists so she is not shown a door that answers one.
    expect(screen.queryByRole("button", { name: "סליקה ותשלומים" })).toBeNull();
  });

  it.each(["reception", "sales_assistant", "seamstress"])(
    "shows %s exactly one row and lands her on the floor",
    async (role) => {
      // ⚠ The count is the assertion, not a detail. F57 ADDED a row rather than
      // widening `board`'s roles to all five, and this is what makes that a test
      // instead of a preference: under the widening she would see «לוח היום»
      // instead, land on a board the server refuses her, and BoardSection's own
      // terminalOf would correctly blank the screen.
      //
      // Landing works with NO edit to useState("dashboard"): `dashboard` is
      // unreachable for her, so `reachable[0]?.key ?? section` picks her single
      // row (App.tsx's activeKey).
      me.mockResolvedValue(staff(role));
      render(<App />);
      await screen.findByRole("navigation");

      expect(navItems()).toEqual(["הצוות בקומה"]);
      expect(screen.queryByRole("button", { name: "לוח היום" })).toBeNull();
      // She is ON the floor section, not merely able to reach it.
      expect(screen.getByRole("heading", { name: "צוות בקומה" })).toBeInTheDocument();
    },
  );

  it("keeps the owner's ten and the shift manager's eight free of the floor row", () => {
    // The floor panel reaches those two roles UNDER «לוח היום», never as a
    // second nav row — spec D11, and the reason there is no eleventh label in
    // NAV_LABELS above.
    expect(NAV_LABELS).not.toContain("הצוות בקומה");
    expect(NAV_LABELS).toHaveLength(10);
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
    expect(navItems()).toEqual(NAV_LABELS.slice(0, 9));
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
    // Scoped by testid since F57: the board screen now carries TWO role="status"
    // regions, because FloorPanel renders beneath the board for these two roles
    // and owns its own cue. An unscoped getByRole("status") is ambiguous, and
    // that ambiguity is the design (D11 forbids sharing state between the two
    // panels) rather than something to collapse.
    expect(screen.getByTestId("board-cue")).toHaveTextContent("טוען את לוח היום…");
    expect(screen.getByTestId("floor-cue")).toBeInTheDocument();
  });
});

describe("the customers section is wired to its nav row", () => {
  it.each(["owner", "shift_manager"])("opens the customer list for a %s", async (role) => {
    // The section's own suite covers its behaviour; this is the render branch,
    // which nothing else would notice was missing — App.tsx can carry the
    // SectionKey, the NAV row and the label and still render nothing.
    me.mockResolvedValue(staff(role));
    render(<App />);
    await screen.findByRole("navigation");

    fireEvent.click(screen.getByRole("button", { name: "לקוחות" }));
    expect(screen.getByRole("heading", { name: "לקוחות" })).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("טוען את רשימת הלקוחות…");
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
