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
      // Same reason, one feature further on: FloorPanel now renders RoomsPanel,
      // whose one-shot client picker fires on mount. Without this row every case
      // below red-fails with `TypeError: api.listFloorClients is not a function`
      // — again naming the nav rather than the floor. NOTHING ELSE in this file
      // moves: F36 adds no nav row, so `NAV_LABELS`, the owner count, the
      // shift-manager slice and the floor-roles count all stay exactly where F53
      // left them, and that is spec AC15's assertion.
      listFloorClients: pending,
      // Same reason, one feature later: clicking «תפירה» mounts AtelierSection,
      // which calls api.getAtelierBoard() on mount. Without this row the render
      // branch test below red-fails with `TypeError: api.getAtelierBoard is not
      // a function` — an error naming the nav rather than the atelier.
      getAtelierBoard: pending,
      gatewayStatus: pending,
      // Same reason again, one feature later. This is the ONE read here that
      // SETTLES, and deliberately: the QR section's loading state is an
      // aria-hidden Skeleton with no accessible content, so against `pending`
      // the render-branch test below could assert nothing but the absence of
      // other sections — which passes just as well when the branch is missing.
      getCheckinQr: vi.fn().mockResolvedValue({
        checkin_url: "https://bella.modryn.co.il/checkin",
        qr_svg: '<svg xmlns="http://www.w3.org/2000/svg" width="37" height="37"></svg>',
      }),
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
  // F41, IMMEDIATELY AFTER the `floor` row in App.tsx's NAV — which is the same
  // slot as "after «לוח היום» and before «צוות»" in this owner-filtered list,
  // because `floor` carries FLOOR_ONLY and the owner never sees it. The two
  // phrasings are not in conflict and neither may be "fixed" against the other.
  //
  // Its roles are owner + shift_manager + SEAMSTRESS, which is why it sits above
  // the owner-only pair, inside the shift manager's slice, and why the seamstress
  // case below is no longer shared with reception and sales assistants.
  "תפירה",
  // F33, after the board and before the owner-only rows. Both console roles
  // reach it: the payload is the public URL printed on a sign in the window and
  // a picture of it, so locking a shift manager out of reprinting a torn poster
  // would be a support ticket for no security gain. In App.tsx's NAV it sits
  // after the `floor` row, which neither of these two roles can see — hence
  // position 10 here and not 11.
  "קוד סריקה",
  // The THREE owner-only rows, last. Everything above is reachable by a shift
  // manager, which is what keeps the assertions below a `.slice(0, 11)`.
  "צוות",
  "סליקה ותשלומים",
  // F20. Owner-only, and that is derivable rather than arbitrary: the panel's
  // FIRST step is the §13 export, which is owner-only on the server, so a shift
  // manager who could open this section would reach no action inside it. Her
  // path to Gate 1 Q4's marketing withdrawal is the customer card, where a
  // front-desk staffer looks a caller up anyway — POST
  // /manage/privacy/marketing-withdraw carries NO route-level gate and inherits
  // the router's (OWNER, SHIFT_MANAGER) one.
  //
  // Appended AFTER «סליקה ותשלומים», so the shift manager's eleven-row prefix is
  // untouched and `.slice(0, 11)` still means what it meant.
  "פרטיות",
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
  it("shows an owner all fourteen sections including Staff, the gateway and privacy", async () => {
    me.mockResolvedValue(staff("owner"));
    render(<App />);
    await screen.findByRole("navigation");
    expect(navItems()).toEqual(NAV_LABELS);
  });

  it("shows a shift manager eleven sections and none of the three owner-only ones", async () => {
    me.mockResolvedValue(staff("shift_manager"));
    render(<App />);
    await screen.findByRole("navigation");
    expect(navItems()).toEqual(NAV_LABELS.slice(0, 11));
    expect(screen.queryByRole("button", { name: "צוות" })).toBeNull();
    // Cosmetics only — the control is the server's owner-only RoleGate, which
    // refuses her on all four /manage/gateway routes with a 403. The filter
    // exists so she is not shown a door that answers one.
    expect(screen.queryByRole("button", { name: "סליקה ותשלומים" })).toBeNull();
    // F20. The row is invisible to her and the server would refuse the section's
    // own first action anyway — but the WITHDRAWAL she does own is reachable, on
    // the customer card, which is what makes hiding this door correct rather
    // than a permission she quietly lost.
    expect(screen.queryByRole("button", { name: "פרטיות" })).toBeNull();
  });

  // ⚠ SPLIT at F41, and the split is the point. This `it.each` used to carry
  // "seamstress" as a third case asserting the same single row; the atelier
  // admits her and no longer does. Leaving her in and widening the expectation
  // would have quietly widened it for reception and sales assistants too, which
  // is the one thing this block exists to pin.
  it.each(["reception", "sales_assistant"])(
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

  it("shows a seamstress the floor panel and the atelier, in that order", async () => {
    // ⚠ THE ORDER IN THIS ASSERTION IS THE WHOLE TEST. It is what fails if the
    // atelier NAV row went in BEFORE `floor` instead of after — which would also
    // move `reachable[0]?.key` and land her on the atelier instead of the floor,
    // with no edit to useState("dashboard") anywhere to say so.
    //
    // Its pair is the owner's thirteen-entry assertion above: give the row
    // FLOOR_ONLY by mistake and that one reds while this one stays green; put
    // the row in the wrong slot and this one reds while that one stays green.
    // Neither number alone pins the row.
    me.mockResolvedValue(staff("seamstress"));
    render(<App />);
    await screen.findByRole("navigation");

    expect(navItems()).toEqual(["הצוות בקומה", "תפירה"]);
    expect(screen.queryByRole("button", { name: "לוח היום" })).toBeNull();
    // Still LANDS on the floor, not on the atelier.
    expect(screen.getByRole("heading", { name: "צוות בקומה" })).toBeInTheDocument();
  });

  it("keeps the owner's fourteen and the shift manager's eleven free of the floor row", () => {
    // The floor panel reaches those two roles UNDER «לוח היום», never as a
    // second nav row — spec D11, and the reason «הצוות בקומה» is absent from
    // NAV_LABELS above even though App.tsx's NAV has fourteen rows.
    //
    // The three numbers in this file's assertions (this length, the owner's
    // count, the shift manager's `.slice(0, 11)`) move TOGETHER every time a row
    // a shift manager can reach is added, and the test NAMES carry them in words
    // as well. F53 moved four of the five and left this one behind, which is why
    // it is spelled out here: a nav row is five coordinated edits, not one.
    expect(NAV_LABELS).not.toContain("הצוות בקומה");
    expect(NAV_LABELS).toHaveLength(14);
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
    expect(navItems()).toEqual(NAV_LABELS.slice(0, 11));
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

describe("the atelier is wired to its nav row", () => {
  it.each(["owner", "shift_manager", "seamstress"])(
    "opens the alteration board for a %s",
    async (role) => {
      // The section's own suite covers its behaviour; this is the RENDER BRANCH,
      // which nothing else would notice was missing — App.tsx can carry the
      // SectionKey, the NAV row, the label and ATELIER_ROLES and still render
      // nothing. All three admitted roles, because this is the one section a
      // seamstress reaches that is not the floor.
      me.mockResolvedValue(staff(role));
      render(<App />);
      await screen.findByRole("navigation");

      fireEvent.click(screen.getByRole("button", { name: "תפירה" }));
      expect(screen.getByRole("heading", { name: "לוח התפירה" })).toBeInTheDocument();
      expect(screen.getByTestId("atelier-cue")).toHaveTextContent("טוען את לוח התפירה…");
    },
  );
});

describe("the check-in code is wired to its nav row", () => {
  it.each(["owner", "shift_manager"])("opens the printable code for a %s", async (role) => {
    // The section's own suite covers its behaviour; this is the render branch
    // plus the both-roles decision, which nothing else would notice was missing.
    // A shift manager who cannot reprint a poster torn off the door is a support
    // call for no security gain — the payload is a public URL and a picture.
    me.mockResolvedValue(staff(role));
    render(<App />);
    await screen.findByRole("navigation");

    fireEvent.click(screen.getByRole("button", { name: "קוד סריקה" }));
    expect(
      await screen.findByRole("heading", { name: "קוד סריקה לרישום לתור" }),
    ).toBeInTheDocument();
    expect(screen.getByText("https://bella.modryn.co.il/checkin")).toBeInTheDocument();
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
