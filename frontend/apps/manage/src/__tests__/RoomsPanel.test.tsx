import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { run } from "axe-core";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import "../i18n";
import type {
  DispatchResult,
  FloorResponse,
  Room,
  RoomAssignment,
  StaffCard,
  WaitlistEntry,
} from "../api";
import { FloorPanel } from "../components/FloorPanel";
import { POLL_INTERVAL_MS } from "../lib/usePoll";

// ⚠ RoomsPanel is mounted THROUGH FloorPanel and never on its own. It is a
// child (spec D15): it owns no timer, no pause control and no announced region,
// so every behaviour this file asserts — the suppressed tick, the terminal 403,
// the shared cue region, the re-arm after a refused action — is only reachable
// with the real parent above it. A direct render would stub exactly the
// mechanisms the panel's correctness depends on.
vi.mock("../api", async () => {
  const actual = await vi.importActual<typeof import("../api")>("../api");
  return {
    ApiError: actual.ApiError,
    errorMessage: actual.errorMessage,
    api: {
      getFloor: vi.fn(),
      startStaffBreak: vi.fn(),
      endStaffBreak: vi.fn(),
      listFloorClients: vi.fn(),
      claimRoom: vi.fn(),
      releaseAssignment: vi.fn(),
      removeAssignmentDress: vi.fn(),
      takeNext: vi.fn(),
    },
  };
});

const { api, ApiError } = await import("../api");
const getFloor = vi.mocked(api.getFloor);
const listFloorClients = vi.mocked(api.listFloorClients);
const claimRoom = vi.mocked(api.claimRoom);
const releaseAssignment = vi.mocked(api.releaseAssignment);
const removeAssignmentDress = vi.mocked(api.removeAssignmentDress);
const takeNext = vi.mocked(api.takeNext);

// 11:07Z is 14:07 in Jerusalem (IDT, UTC+3); the test script pins
// TZ=America/New_York, so an unzoned read prints 07:07 and every time assertion
// below fails loudly rather than quietly.
const NOW = "2026-08-04T11:07:00Z";
const ASSIGNED_AT = "2026-08-04T10:25:00Z"; // 42 minutes before NOW

const SELF_ID = "11111111-1111-1111-1111-111111111111";
const OTHER_ID = "22222222-2222-2222-2222-222222222222";
const ROOM_A = "aaaaaaaa-0000-0000-0000-000000000001";
const ROOM_B = "bbbbbbbb-0000-0000-0000-000000000002";
const ASSIGNMENT_ID = "cccccccc-0000-0000-0000-000000000003";
const BINDING_ID = "dddddddd-0000-0000-0000-000000000004";
const BOOKING_ID = "eeeeeeee-0000-0000-0000-000000000005";
const TICKET_ID = "ffffffff-0000-0000-0000-000000000006";

function staff(overrides: Partial<StaffCard> = {}): StaffCard {
  return {
    id: SELF_ID,
    display_name: "רותם",
    role: "owner",
    status: "available",
    break_started_at: null,
    occupancy: null,
    ...overrides,
  };
}

function assignment(overrides: Partial<RoomAssignment> = {}): RoomAssignment {
  return {
    id: ASSIGNMENT_ID,
    staff_user_id: OTHER_ID,
    staff_display_name: "דנה כהן",
    staff_role: "seamstress",
    client_label: "מיכל",
    booking_id: BOOKING_ID,
    assigned_at: ASSIGNED_AT,
    dresses: [],
    ...overrides,
  };
}

function room(overrides: Partial<Room> = {}): Room {
  return {
    id: ROOM_A,
    label: "חדר 1",
    sort_order: 0,
    is_active: true,
    assignment: null,
    ...overrides,
  };
}

function waiting(overrides: Partial<WaitlistEntry> = {}): WaitlistEntry {
  return {
    id: TICKET_ID,
    name: "נועה בר",
    visit_type: "bride",
    position: 1,
    arrived_at: ASSIGNED_AT,
    called: false,
    skip_count: 0,
    duplicate: false,
    ...overrides,
  };
}

// ⚠ The third argument is F58's, and its DEFAULT is the empty queue — every
// shipped call above stays byte-identical and keeps rendering a floor with no
// «קחי את הבאה» on any tile, which is exactly the state they were written
// against.
function floor(
  rooms: Room[],
  cards: StaffCard[] = [staff()],
  entries: WaitlistEntry[] = [],
): FloorResponse {
  return { staff: cards, rooms, server_now: NOW, waitlist: { entries, truncated: false } };
}

function dispatched(next: Room, entries: WaitlistEntry[] = []): DispatchResult {
  return { room: next, waitlist: { entries, truncated: false } };
}

function mount(props: { selfId?: string; role?: string } = {}) {
  return render(<FloorPanel selfId={props.selfId ?? SELF_ID} role={props.role ?? "owner"} />);
}

// Tiles are keyed by room id and carry it as a data attribute — the same shape
// FloorPanel's cards use, and what the departing-tile focus rescue reads.
function tile(id: string): HTMLElement {
  const node = document.querySelector(`[data-room-id="${id}"]`);
  if (node === null) {
    throw new Error(`no tile for room ${id}`);
  }
  return node as HTMLElement;
}

beforeEach(() => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  vi.setSystemTime(new Date(NOW));
  getFloor.mockReset();
  listFloorClients.mockReset();
  claimRoom.mockReset();
  releaseAssignment.mockReset();
  removeAssignmentDress.mockReset();
  takeNext.mockReset();
  listFloorClients.mockResolvedValue({ clients: [], truncated: false });
});

afterEach(() => {
  vi.useRealTimers();
});

async function advance(ms: number) {
  await act(async () => {
    vi.advanceTimersByTime(ms);
  });
}

// --- R-empty, R, R-inactive, R-ghost: every state, not just the happy one ----

describe("the four tiles and the two empty states", () => {
  it("renders the rooms heading in EVERY state, including the empty one", async () => {
    // DC-10. The h3 is move 3's and move 6's focus-rescue target, so it may not
    // be conditional on there being tiles — deleting your only room returns the
    // panel to the EmptyState and the rescue target must survive the transition.
    getFloor.mockResolvedValue(floor([]));
    mount();

    await screen.findByRole("heading", { level: 3, name: "חדרי מדידה" });
    expect(screen.getByText("עדיין לא הוגדרו חדרי מדידה")).toBeInTheDocument();

    getFloor.mockResolvedValue(floor([room()]));
    await advance(POLL_INTERVAL_MS);

    await screen.findByText("חדר 1");
    expect(screen.getByRole("heading", { level: 3, name: "חדרי מדידה" })).toBeInTheDocument();
  });

  it("offers the empty state's CTA to an owner and NOTHING but the title to a seamstress", async () => {
    // A seamstress cannot fix it, and pointing her at a door that answers 403 is
    // the trap §2.2 exists to avoid. No body in either case.
    getFloor.mockResolvedValue(floor([]));
    const owner = mount();
    await screen.findByText("עדיין לא הוגדרו חדרי מדידה");
    expect(screen.getByRole("button", { name: "הוספת חדר" })).toBeInTheDocument();
    owner.unmount();

    mount({ role: "seamstress" });
    await screen.findByText("עדיין לא הוגדרו חדרי מדידה");
    expect(screen.queryByRole("button", { name: "הוספת חדר" })).toBeNull();
    expect(screen.queryByRole("button", { name: "ניהול חדרים" })).toBeNull();
  });

  it("reads «פנוי» on a free room and offers the claim, never «פנויה»", async () => {
    // A room and a staffer are different subjects: the two words must not look
    // like one word inflected by accident.
    getFloor.mockResolvedValue(floor([room()]));
    mount();
    await screen.findByText("חדר 1");

    const item = tile(ROOM_A);
    expect(within(item).getByText("פנוי")).toBeInTheDocument();
    expect(within(item).queryByText("פנויה")).toBeNull();
    expect(within(item).getByRole("button", { name: "תפיסת החדר — חדר 1" })).toHaveTextContent(
      "תפיסת החדר",
    );
  });

  it("reads «תפוס», the holder, her role as muted words, the LABELLED client and the elapsed line", async () => {
    getFloor.mockResolvedValue(
      floor([
        room({
          assignment: assignment({
            dresses: [
              { id: BINDING_ID, dress_id: "d1", dress_name: "ורוניק", dress_size: "38" },
              { id: "b2", dress_id: "d2", dress_name: "סברינה", dress_size: null },
            ],
          }),
        }),
      ]),
    );
    mount();
    await screen.findByText("דנה כהן");

    const item = tile(ROOM_A);
    expect(within(item).getByText("תפוס")).toBeInTheDocument();
    // The role is muted WORDS and never a second Badge — the tile's one pill is
    // the occupancy (P-2).
    expect(within(item).getByText("תופרת")).toBeInTheDocument();
    expect(item.querySelectorAll(".rounded-full")).toHaveLength(1);
    // The client's name is LABELLED, never a bare name one line under another.
    expect(within(item).getByText("לקוחה")).toBeInTheDocument();
    expect(within(item).getByText("מיכל")).toBeInTheDocument();
    expect(item.textContent).toContain("כבר 42 דק'");
    expect(within(item).getByText("שמלות בחדר")).toBeInTheDocument();
    expect(within(item).getByText("ורוניק")).toBeInTheDocument();
    expect(item.textContent).toContain("38");
    // A gown with no size bound renders the name alone — no dangling separator.
    expect(within(item).getByRole("button", { name: "הסרה — סברינה" })).toBeInTheDocument();
  });

  it("renders «ללא לקוחה מקושרת» for an anonymous assignment, which is the DEFAULT claim", async () => {
    getFloor.mockResolvedValue(
      floor([room({ assignment: assignment({ client_label: null, booking_id: null }) })]),
    );
    mount();
    await screen.findByText("דנה כהן");

    const item = tile(ROOM_A);
    expect(within(item).getByText("ללא לקוחה מקושרת")).toBeInTheDocument();
    expect(within(item).queryByText("לקוחה")).toBeNull();
  });

  it("renders «זה עתה» for the first minute rather than «כבר 0 דק'»", async () => {
    getFloor.mockResolvedValue(
      floor([room({ assignment: assignment({ assigned_at: NOW }) })]),
    );
    mount();
    await screen.findByText("דנה כהן");

    const item = tile(ROOM_A);
    expect(item.textContent).toContain("זה עתה");
    expect(item.textContent).not.toContain("כבר");
  });

  it("omits the dress group label entirely when nothing is bound", async () => {
    getFloor.mockResolvedValue(floor([room({ assignment: assignment() })]));
    mount();
    await screen.findByText("דנה כהן");

    expect(within(tile(ROOM_A)).queryByText("שמלות בחדר")).toBeNull();
  });

  it("says the holder is gone, drops the role line and keeps the client and the dresses", async () => {
    // F51's soft_delete has no interaction rule with an open assignment, so a
    // staffer removed mid-fitting leaves a live assignment with no card.
    getFloor.mockResolvedValue(
      floor([
        room({
          assignment: assignment({
            staff_display_name: null,
            staff_role: null,
            dresses: [
              { id: BINDING_ID, dress_id: "d1", dress_name: "ורוניק", dress_size: "38" },
            ],
          }),
        }),
      ]),
    );
    mount();
    await screen.findByText("אשת הצוות שתפסה את החדר כבר לא ברשימה.");

    const item = tile(ROOM_A);
    expect(within(item).queryByText("תופרת")).toBeNull();
    // Facts about the ROOM survive; only the person is unknown.
    expect(within(item).getByText("מיכל")).toBeInTheDocument();
    expect(within(item).getByText("ורוניק")).toBeInTheDocument();
  });

  it("renders NO role line for a role string lib/roles.ts does not recognise", async () => {
    // DC-12. roleLabelKey returns `string | null`, and the tile takes the OMIT
    // branch: a raw slug under a Hebrew name on a tile is noise, where on a
    // staff card it is the only thing distinguishing two cards.
    getFloor.mockResolvedValue(
      floor([room({ assignment: assignment({ staff_role: "concierge" }) })]),
    );
    mount();
    await screen.findByText("דנה כהן");

    expect(tile(ROOM_A).textContent).not.toContain("concierge");
  });

  it("greys an out-of-service room with the WORD, offers no claim, and uses NO opacity utility", async () => {
    // Opacity multiplies every contrast ratio inside the element, and axe
    // computes contrast against DECLARED colours rather than composited pixels —
    // so it walks past the whole class. Greying is a token swap.
    getFloor.mockResolvedValue(floor([room({ is_active: false })]));
    mount();
    await screen.findByText("חדר 1");

    const item = tile(ROOM_A);
    expect(within(item).getByText("מחוץ לשירות")).toBeInTheDocument();
    expect(within(item).queryByRole("button", { name: /תפיסת החדר/ })).toBeNull();
    expect(item.innerHTML).not.toMatch(/opacity-/);
    expect(item.querySelector("bdi")).toHaveClass("text-ink-muted");
  });

  it("lets the occupancy win the Badge on a deactivated room and puts «מחוץ לשירות» on its own line", async () => {
    // A person is standing in that room; a screen that puts «מחוץ לשירות» where
    // «תפוס» belongs denies something a shift manager can see through the
    // curtain. One Badge, both facts.
    getFloor.mockResolvedValue(
      floor([room({ is_active: false, assignment: assignment() })]),
    );
    mount();
    await screen.findByText("דנה כהן");

    const item = tile(ROOM_A);
    expect(within(item).getByText("תפוס")).toBeInTheDocument();
    expect(within(item).getByText("מחוץ לשירות")).toBeInTheDocument();
    expect(item.querySelectorAll(".rounded-full")).toHaveLength(1);
  });

  it("renders the server's order and never re-sorts it", async () => {
    getFloor.mockResolvedValue(
      floor([
        room({ id: ROOM_B, label: "הבמה", sort_order: 2 }),
        room({ id: ROOM_A, label: "חדר 1", sort_order: 0 }),
      ]),
    );
    mount();
    await screen.findByText("הבמה");

    const labels = Array.from(document.querySelectorAll("[data-room-id]")).map(
      (node) => node.getAttribute("data-room-id"),
    );
    expect(labels).toEqual([ROOM_B, ROOM_A]);
  });
});

// --- AC21: which control EXISTS is the rendered form of the two axes ----------

describe("AC21 — absence, never a disabled control", () => {
  const busyFloor = () =>
    floor([
      room({
        assignment: assignment({
          dresses: [{ id: BINDING_ID, dress_id: "d1", dress_name: "ורוניק", dress_size: null }],
        }),
      }),
      room({ id: ROOM_B, label: "הבמה" }),
    ]);

  it("shows an owner all four elevated controls", async () => {
    getFloor.mockResolvedValue(busyFloor());
    mount();
    await screen.findByText("דנה כהן");

    expect(screen.getByRole("button", { name: "ניהול חדרים" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "העברה לעמיתה — חדר 1" })).toBeInTheDocument();
    // A colleague's room: elevated callers may release it, the holder may, and
    // nobody else.
    expect(screen.getByRole("button", { name: "שחרור — חדר 1" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "הוספת שמלה — חדר 1" })).toBeInTheDocument();
  });

  it("shows a seamstress NONE of them — and no disabled control and no lock glyph", async () => {
    // ⚠ This is what keeps P-6's 403-is-terminal rule unreachable by DESIGN
    // rather than by luck: a 403 stops the loop permanently and clears the
    // panel, so a seamstress who tapped a control the server will refuse would
    // get a blank screen and a reload button — for the three floor roles, the
    // whole product going dark.
    getFloor.mockResolvedValue(busyFloor());
    mount({ role: "seamstress" });
    await screen.findByText("דנה כהן");

    expect(screen.queryByRole("button", { name: "ניהול חדרים" })).toBeNull();
    expect(screen.queryByRole("button", { name: /העברה לעמיתה/ })).toBeNull();
    expect(screen.queryByRole("button", { name: /שחרור/ })).toBeNull();
    // Absence, not disablement: a disabled control with no explanation is worse
    // than an absent one.
    const disabled = Array.from(document.querySelectorAll("button")).filter(
      (node) => node.disabled,
    );
    expect(disabled).toHaveLength(0);
  });

  it("leaves BOTH dress controls open to a seamstress, with no ownership check", async () => {
    // A colleague fetching a second gown for a fitting already in progress is
    // the normal case on a shop floor, and binding a dress is not a destructive
    // act on the holder's room (spec D4). `removed_by` is the accountability.
    getFloor.mockResolvedValue(busyFloor());
    mount({ role: "seamstress" });
    await screen.findByText("דנה כהן");

    expect(screen.getByRole("button", { name: "הוספת שמלה — חדר 1" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "הסרה — ורוניק" })).toBeInTheDocument();
    // …and she may still claim a free room and release her OWN.
    expect(screen.getByRole("button", { name: "תפיסת החדר — הבמה" })).toBeInTheDocument();
  });

  it("gives the HOLDER a release control on her own room without an elevated role", async () => {
    getFloor.mockResolvedValue(
      floor([room({ assignment: assignment({ staff_user_id: SELF_ID }) })]),
    );
    mount({ role: "seamstress" });
    await screen.findByText("דנה כהן");

    expect(screen.getByRole("button", { name: "שחרור — חדר 1" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /העברה לעמיתה/ })).toBeNull();
  });
});

// --- the claim, the release and the dress removal ----------------------------

describe("the mutations patch from the server's row", () => {
  it("patches the tile from the claim's response and announces the ROOM", async () => {
    getFloor.mockResolvedValue(floor([room()]));
    claimRoom.mockResolvedValue(room({ assignment: assignment({ staff_user_id: SELF_ID }) }));
    mount();
    await screen.findByText("חדר 1");

    fireEvent.click(screen.getByRole("button", { name: "תפיסת החדר — חדר 1" }));

    await waitFor(() => expect(screen.getByText("דנה כהן")).toBeInTheDocument());
    expect(claimRoom).toHaveBeenCalledWith(ROOM_A, {});
    expect(screen.getByTestId("floor-cue")).toHaveTextContent("החדר נתפס: חדר 1.");
    // ⚠ The cue names the ROOM and never the client: the region is PERSISTENT,
    // so a bride's name in it would sit on a five-role screen for an arbitrary
    // length of time.
    expect(screen.getByTestId("floor-cue").textContent).not.toContain("מיכל");
  });

  it("sends the chosen booking id and refetches the client list after the claim", async () => {
    listFloorClients.mockResolvedValue({
      clients: [{ booking_id: BOOKING_ID, client_label: "מיכל", starts_at: NOW }],
      truncated: false,
    });
    getFloor.mockResolvedValue(floor([room()]));
    claimRoom.mockResolvedValue(room({ assignment: assignment() }));
    mount();
    await screen.findByText("חדר 1");
    await waitFor(() => expect(screen.getByRole("combobox")).toBeInTheDocument());

    fireEvent.change(screen.getByRole("combobox"), { target: { value: BOOKING_ID } });
    fireEvent.click(screen.getByRole("button", { name: "תפיסת החדר — חדר 1" }));

    await waitFor(() => expect(claimRoom).toHaveBeenCalledWith(ROOM_A, { booking_id: BOOKING_ID }));
    // Two triggers and no timer: mount, and each successful claim.
    await waitFor(() => expect(listFloorClients).toHaveBeenCalledTimes(2));
  });

  it("hides the client picker entirely when the list is empty, and claims anonymously", async () => {
    // Absent, not empty: a <select> with zero real options is a dead control
    // that looks live, and the anonymous claim is the DEFAULT path.
    getFloor.mockResolvedValue(floor([room()]));
    mount();
    await screen.findByText("חדר 1");

    expect(screen.queryByRole("combobox")).toBeNull();
    expect(screen.getByRole("button", { name: "תפיסת החדר — חדר 1" })).toBeInTheDocument();
  });

  it("hides the picker and never blocks the claim when the client list FAILS", async () => {
    listFloorClients.mockRejectedValue(new ApiError(500, "SERVER_ERROR", "boom"));
    getFloor.mockResolvedValue(floor([room()]));
    mount();
    await screen.findByText("חדר 1");

    expect(screen.queryByRole("combobox")).toBeNull();
    expect(screen.getByRole("button", { name: "תפיסת החדר — חדר 1" })).toBeInTheDocument();
    // A failed picker is not an outage the tile reports: the claim proceeds.
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("names no count and no limit on a truncated client list", async () => {
    listFloorClients.mockResolvedValue({
      clients: [{ booking_id: BOOKING_ID, client_label: "מיכל", starts_at: NOW }],
      truncated: true,
    });
    getFloor.mockResolvedValue(floor([room()]));
    mount();
    await screen.findByText("חדר 1");

    const line = await screen.findByText(/הרשימה חלקית/);
    expect(line.textContent).not.toMatch(/\d/);
  });

  it("fires ONE request on a double tap and disables the control while it is in flight", async () => {
    getFloor.mockResolvedValue(floor([room()]));
    let settle: (value: Room) => void = () => {};
    claimRoom.mockReturnValue(
      new Promise<Room>((resolve) => {
        settle = resolve;
      }),
    );
    mount();
    await screen.findByText("חדר 1");

    const control = screen.getByRole("button", { name: "תפיסת החדר — חדר 1" });
    fireEvent.click(control);
    fireEvent.click(control);

    expect(claimRoom).toHaveBeenCalledTimes(1);
    expect(control).toBeDisabled();
    settle(room({ assignment: assignment() }));
    await waitFor(() => expect(screen.getByText("דנה כהן")).toBeInTheDocument());
  });

  it("releases from the tile and announces the room", async () => {
    getFloor.mockResolvedValue(floor([room({ assignment: assignment() })]));
    releaseAssignment.mockResolvedValue(room());
    mount();
    await screen.findByText("דנה כהן");

    fireEvent.click(screen.getByRole("button", { name: "שחרור — חדר 1" }));

    await waitFor(() => expect(screen.getByText("פנוי")).toBeInTheDocument());
    expect(releaseAssignment).toHaveBeenCalledWith(ASSIGNMENT_ID);
    expect(screen.getByTestId("floor-cue")).toHaveTextContent("החדר שוחרר: חדר 1.");
    // Just-released is not a state — it is the free tile, arrived at. No fade,
    // no highlight, no "released" flash.
    expect(screen.queryByText("דנה כהן")).toBeNull();
  });

  it("removes a dress and names the DRESS in the cue", async () => {
    getFloor.mockResolvedValue(
      floor([
        room({
          assignment: assignment({
            dresses: [{ id: BINDING_ID, dress_id: "d1", dress_name: "ורוניק", dress_size: "38" }],
          }),
        }),
      ]),
    );
    removeAssignmentDress.mockResolvedValue(room({ assignment: assignment() }));
    mount();
    await screen.findByText("ורוניק");

    fireEvent.click(screen.getByRole("button", { name: "הסרה — ורוניק" }));

    await waitFor(() =>
      expect(removeAssignmentDress).toHaveBeenCalledWith(ASSIGNMENT_ID, BINDING_ID),
    );
    expect(screen.getByTestId("floor-cue")).toHaveTextContent("השמלה הוסרה מהחדר: ורוניק.");
  });
});

// --- the 409 loser's screen --------------------------------------------------

describe("R-taken — she tapped claim and someone beat her", () => {
  it("NAMES the occupant in the tile, in the notice register, and leaves the tile interactive", async () => {
    // ⚠ The screen the feature exists to deliver. It must name a person and it
    // must not look like an error page: the tile stays «פנוי» because the panel
    // is NOT optimistic, the claim control does not vanish (a control that
    // disappears on a refusal teaches her the screen punishes trying), and the
    // next unforced tick repaints the tile into an occupied one showing exactly
    // the person this sentence named.
    getFloor.mockResolvedValue(floor([room()]));
    claimRoom.mockRejectedValue(
      new ApiError(409, "ROOM_OCCUPIED", "taken", { staff_display_name: "דנה כהן" }),
    );
    mount();
    await screen.findByText("חדר 1");

    fireEvent.click(screen.getByRole("button", { name: "תפיסת החדר — חדר 1" }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("דנה כהן כבר בחדר הזה.");
    // NEVER red: two staffers reaching for one curtain is the ordinary shop
    // floor, and nothing that can go wrong here is her fault.
    expect(alert).toHaveClass("text-warning-text");
    expect(alert.className).not.toContain("text-danger");
    // …in the TILE, not a banner: with five tiles a panel-level error would
    // make her hunt for which one refused her.
    expect(alert.closest("[data-room-id]")).toBe(tile(ROOM_A));
    expect(screen.getByRole("button", { name: "תפיסת החדר — חדר 1" })).toBeEnabled();
    // Her name renders in a bare <bdi>, never dir="ltr".
    expect(alert.querySelector("bdi")).toHaveTextContent("דנה כהן");
    expect(alert.querySelector("bdi")).not.toHaveAttribute("dir");
  });

  it("admits it does not know rather than naming nobody when the 409 carries no details", async () => {
    // The winner released between the index violation and the occupant read —
    // a real branch the backend pins with its own db test. An empty
    // interpolation on a legally binding surface is worse than a sentence that
    // says it does not know.
    getFloor.mockResolvedValue(floor([room()]));
    claimRoom.mockRejectedValue(new ApiError(409, "ROOM_OCCUPIED", "taken"));
    mount();
    await screen.findByText("חדר 1");

    fireEvent.click(screen.getByRole("button", { name: "תפיסת החדר — חדר 1" }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("החדר נתפס זה עתה. נסי שוב.");
    expect(alert.textContent).not.toContain("כבר בחדר הזה");
  });

  it("gives STAFF_OCCUPIED a DIFFERENT sentence naming the other room", async () => {
    // A different remedy: release the other room, not take another one. The
    // colon appositive keeps the label off a Hebrew preposition — «בחדר
    // {{room}}» would render «בחדר חדר 2».
    getFloor.mockResolvedValue(floor([room()]));
    claimRoom.mockRejectedValue(
      new ApiError(409, "STAFF_OCCUPIED", "hers", { room_label: "הבמה" }),
    );
    mount();
    await screen.findByText("חדר 1");

    fireEvent.click(screen.getByRole("button", { name: "תפיסת החדר — חדר 1" }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("היא כבר בחדר אחר: הבמה.");
    expect(alert.querySelector("bdi")).toHaveTextContent("הבמה");
  });

  it("falls back to the strict PREFIX form when that 409 carries no details", async () => {
    getFloor.mockResolvedValue(floor([room()]));
    claimRoom.mockRejectedValue(new ApiError(409, "STAFF_OCCUPIED", "hers"));
    mount();
    await screen.findByText("חדר 1");

    fireEvent.click(screen.getByRole("button", { name: "תפיסת החדר — חדר 1" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("היא כבר בחדר אחר.");
  });

  it("clears the alert on the very next tick and repaints the tile into an occupied one", async () => {
    // The alert keeps its own promise inside five seconds. That convergence is
    // the design answer to "does it look broken".
    getFloor.mockResolvedValue(floor([room()]));
    claimRoom.mockRejectedValue(
      new ApiError(409, "ROOM_OCCUPIED", "taken", { staff_display_name: "דנה כהן" }),
    );
    mount();
    await screen.findByText("חדר 1");

    fireEvent.click(screen.getByRole("button", { name: "תפיסת החדר — חדר 1" }));
    await screen.findByRole("alert");

    getFloor.mockResolvedValue(floor([room({ assignment: assignment() })]));
    await advance(POLL_INTERVAL_MS);

    await waitFor(() => expect(screen.queryByRole("alert")).toBeNull());
    expect(within(tile(ROOM_A)).getByText("תפוס")).toBeInTheDocument();
    expect(within(tile(ROOM_A)).getByText("דנה כהן")).toBeInTheDocument();
  });
});

// --- R-gone, the outage fallback, and the two terminal rules -----------------

describe("the 404s, the outage register and P-6", () => {
  it("names the ROOM's disappearance on a claim and is NOT terminal", async () => {
    getFloor.mockResolvedValue(floor([room()]));
    claimRoom.mockRejectedValue(new ApiError(404, "NOT_FOUND", "gone"));
    mount();
    await screen.findByText("חדר 1");

    fireEvent.click(screen.getByRole("button", { name: "תפיסת החדר — חדר 1" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "החדר כבר לא זמין. הרשימה תתוקן בעדכון הבא.",
    );
    // Not terminal: the panel, the tiles and the pause control all survive.
    expect(screen.getByText("חדר 1")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "השהיה — עדכון הצוות" })).toBeInTheDocument();
  });

  it("names the ASSIGNMENT's disappearance on a release — a different sentence", async () => {
    // «החדר כבר לא זמין» is actively misleading when the room is fine and the
    // fitting simply ended.
    getFloor.mockResolvedValue(floor([room({ assignment: assignment() })]));
    releaseAssignment.mockRejectedValue(new ApiError(404, "NOT_FOUND", "gone"));
    mount();
    await screen.findByText("דנה כהן");

    fireEvent.click(screen.getByRole("button", { name: "שחרור — חדר 1" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "הלקוחה כבר לא בחדר. הרשימה תתוקן בעדכון הבא.",
    );
  });

  it("promises no NEXT UPDATE while the panel is PAUSED", async () => {
    // DC-8. pause() stops the loop and the claim stays fully available, so a
    // 404 then renders a sentence the screen will not keep. §0 rule 4 was
    // written against durations; this is the same failure in the EVENT form.
    //
    // MUTATION: drop the `paused` branch and the running sentence appears on a
    // stopped panel.
    getFloor.mockResolvedValue(floor([room()]));
    claimRoom.mockRejectedValue(new ApiError(404, "NOT_FOUND", "gone"));
    mount();
    await screen.findByText("חדר 1");

    fireEvent.click(screen.getByRole("button", { name: "השהיה — עדכון הצוות" }));
    fireEvent.click(screen.getByRole("button", { name: "תפיסת החדר — חדר 1" }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("חידוש");
    expect(alert.textContent).not.toContain("בעדכון הבא");
  });

  it("falls through to the shipped outage sentence, muted, on anything unmapped", async () => {
    getFloor.mockResolvedValue(floor([room()]));
    claimRoom.mockRejectedValue(new ApiError(500, "SERVER_ERROR", "boom"));
    mount();
    await screen.findByText("חדר 1");

    fireEvent.click(screen.getByRole("button", { name: "תפיסת החדר — חדר 1" }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("לא הצלחנו לטעון את רשימת הצוות כרגע.");
    // The OUTAGE register — muted, not the notice colour, and never danger.
    expect(alert).toHaveClass("text-ink-muted");
  });

  it("keeps the loop POLLING after a refused action", async () => {
    // ⚠ The re-arm lives in mutate()'s .finally(), not on its success path: a
    // refused action must not park the loop or the panel silently stops
    // converging the first time anybody acts.
    getFloor.mockResolvedValue(floor([room()]));
    claimRoom.mockRejectedValue(new ApiError(409, "ROOM_OCCUPIED", "taken"));
    mount();
    await screen.findByText("חדר 1");

    fireEvent.click(screen.getByRole("button", { name: "תפיסת החדר — חדר 1" }));
    await screen.findByRole("alert");
    const before = getFloor.mock.calls.length;

    await advance(POLL_INTERVAL_MS);
    expect(getFloor.mock.calls.length).toBeGreaterThan(before);
  });

  it("a room action's 403 is TERMINAL for the whole panel (P-6)", async () => {
    // Unreachable by design — §2.2 renders no control the caller may not use —
    // and correct when it happens: the alternative is an in-tile alert plus a
    // loop that keeps polling with a role the server just refused.
    getFloor.mockResolvedValue(floor([room()]));
    claimRoom.mockRejectedValue(new ApiError(403, "NOT_AUTHORIZED", "no"));
    mount();
    await screen.findByText("חדר 1");

    fireEvent.click(screen.getByRole("button", { name: "תפיסת החדר — חדר 1" }));

    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent("אין הרשאה לצפות ברשימת הצוות"),
    );
    expect(screen.queryByText("חדר 1")).toBeNull();
  });
});

// --- DC-4: the inline picker's state contract --------------------------------

describe("DC-4 — the free tile's client selection survives the tick", () => {
  it("leaves a selection on ANOTHER tile alone when a tick reorders the list", async () => {
    // The selection is local state keyed by ROOM ID; tiles are keyed by room id
    // too, so React preserves the subtree and a repaint mutates text nodes
    // inside a stable element.
    //
    // MUTATION: key the state by INDEX and this reddens — the tick's reorder
    // moves the selection onto the wrong room.
    listFloorClients.mockResolvedValue({
      clients: [
        { booking_id: BOOKING_ID, client_label: "מיכל", starts_at: NOW },
        { booking_id: "f0000000-0000-0000-0000-000000000006", client_label: "רות", starts_at: NOW },
      ],
      truncated: false,
    });
    const first = [room({ id: ROOM_A, label: "חדר 1" }), room({ id: ROOM_B, label: "הבמה" })];
    getFloor.mockResolvedValue(floor(first));
    mount();
    await screen.findByText("הבמה");

    const pickerB = within(tile(ROOM_B)).getByRole("combobox");
    fireEvent.change(pickerB, { target: { value: BOOKING_ID } });
    expect(pickerB).toHaveValue(BOOKING_ID);

    getFloor.mockResolvedValue(floor([first[1], first[0]]));
    await advance(POLL_INTERVAL_MS);

    await waitFor(() =>
      expect(
        Array.from(document.querySelectorAll("[data-room-id]")).map((n) =>
          n.getAttribute("data-room-id"),
        ),
      ).toEqual([ROOM_B, ROOM_A]),
    );
    expect(within(tile(ROOM_B)).getByRole("combobox")).toHaveValue(BOOKING_ID);
    expect(within(tile(ROOM_A)).getByRole("combobox")).toHaveValue("");
  });
});

// --- the announced region ----------------------------------------------------

describe("the shared cue region", () => {
  it("does NOT change across several consecutive ticks with a room cue populated", async () => {
    // ⚠ F34's F-7. Assigning a BYTE-IDENTICAL string to a text node still
    // produces a real childList mutation inside role="status", and a
    // single-tick assertion passes against the broken version whenever the cue
    // starts empty — so this populates it first and then drives three ticks.
    getFloor.mockResolvedValue(floor([room()]));
    claimRoom.mockResolvedValue(room({ assignment: assignment() }));
    mount();
    await screen.findByText("חדר 1");

    fireEvent.click(screen.getByRole("button", { name: "תפיסת החדר — חדר 1" }));
    await waitFor(() =>
      expect(screen.getByTestId("floor-cue")).toHaveTextContent("החדר נתפס"),
    );
    const populated = screen.getByTestId("floor-cue").textContent;

    getFloor.mockResolvedValue(floor([room({ assignment: assignment() })]));
    await advance(POLL_INTERVAL_MS);
    await advance(POLL_INTERVAL_MS);
    await advance(POLL_INTERVAL_MS);

    expect(screen.getByTestId("floor-cue").textContent).toBe(populated);
  });

  it("says nothing at all when a COLLEAGUE claims a room", async () => {
    // A room claimed, released or handed over by somebody else repaints its
    // tile silently. The poll may never write into role="status".
    getFloor.mockResolvedValue(floor([room()]));
    mount();
    await screen.findByText("חדר 1");
    const before = screen.getByTestId("floor-cue").textContent;

    getFloor.mockResolvedValue(floor([room({ assignment: assignment() })]));
    await advance(POLL_INTERVAL_MS);

    await waitFor(() => expect(screen.getByText("דנה כהן")).toBeInTheDocument());
    expect(screen.getByTestId("floor-cue").textContent).toBe(before);
  });
});

// --- the six focus moves -----------------------------------------------------

describe("focus — axe can see none of this", () => {
  it("MOVE 1 — a refused action moves focus into the tile's alert", async () => {
    // ⚠ THE FAILURE PATH IS THE ONE THAT GETS FORGOTTEN — this bug class has
    // shipped three times in this repo and axe walked past all three.
    //
    // MUTATION: delete the [tileError] effect.
    getFloor.mockResolvedValue(floor([room()]));
    claimRoom.mockRejectedValue(
      new ApiError(409, "ROOM_OCCUPIED", "taken", { staff_display_name: "דנה כהן" }),
    );
    mount();
    await screen.findByText("חדר 1");

    const control = screen.getByRole("button", { name: "תפיסת החדר — חדר 1" });
    control.focus();
    fireEvent.click(control);

    await waitFor(() => {
      const alert = screen.getByRole("alert");
      expect(alert).toHaveTextContent("דנה כהן כבר בחדר הזה.");
      expect(document.activeElement).toBe(alert);
    });
  });

  it("MOVE 2 — a successful action hands focus back to the tile's CURRENT control", async () => {
    // ⚠ jsdom IS THE TRAP and F57's own success-path focus test was VACUOUS
    // because of it: jsdom does not blur a disabled element, so activeElement
    // never became <body>, the body guard never passed, and the whole restore
    // effect could be deleted with the suite green. This test blurs
    // EXPLICITLY, reproducing what a real browser does when `disabled` is set
    // — @boutique/ui's Button is disabled={disabled || loading} and every room
    // action is that shape.
    //
    // The control also does not survive: a claim replaces «תפיסת החדר» and its
    // Select with «שחרור», so the ref Map is keyed by ROOM ID and resolves to
    // whatever the tile's primary control currently is.
    //
    // MUTATION: delete the [busyIds] restore effect — focus stays on <body>.
    getFloor.mockResolvedValue(floor([room()]));
    let settle: (value: Room) => void = () => {};
    claimRoom.mockReturnValue(
      new Promise<Room>((resolve) => {
        settle = resolve;
      }),
    );
    mount();
    await screen.findByText("חדר 1");

    const control = screen.getByRole<HTMLButtonElement>("button", {
      name: "תפיסת החדר — חדר 1",
    });
    control.focus();
    fireEvent.click(control);
    expect(control).toBeDisabled();
    // ⚠ jsdom's blur() BAILS on a non-focusable element, and `disabled` makes
    // this one non-focusable — so `control.blur()` on its own is a silent no-op
    // and the assertion below would hold with the whole restore effect deleted.
    // Re-enabling for the length of one call is what makes the blur a real
    // browser performs actually happen here.
    control.disabled = false;
    control.blur();
    expect(document.activeElement).toBe(document.body);

    await act(async () => {
      settle(room({ assignment: assignment({ staff_user_id: SELF_ID }) }));
    });

    await waitFor(() =>
      expect(document.activeElement).toHaveAccessibleName("שחרור — חדר 1"),
    );
  });

  it("MOVE 3 — a tile deleted by a TICK hands focus to the rooms heading", async () => {
    // ⚠ DC-6. The premise "the only way a tile leaves is a registry delete" is
    // wrong, and the wrong reading puts the fix in the wrong file: a tile also
    // leaves via a TICK — another elevated user deleting a room from her own
    // device — which arrives through the rooms payload and not through this
    // user's delete handler.
    //
    // MUTATION: delete the departing-tile check.
    getFloor.mockResolvedValue(
      floor([room({ id: ROOM_A }), room({ id: ROOM_B, label: "הבמה" })]),
    );
    mount();
    await screen.findByText("הבמה");

    within(tile(ROOM_B)).getByRole("button", { name: "תפיסת החדר — הבמה" }).focus();

    getFloor.mockResolvedValue(floor([room({ id: ROOM_A })]));
    await advance(POLL_INTERVAL_MS);

    await waitFor(() => expect(screen.queryByText("הבמה")).toBeNull());
    expect(document.activeElement).not.toBe(document.body);
    expect(document.activeElement).toBe(
      screen.getByRole("heading", { level: 3, name: "חדרי מדידה" }),
    );
  });

  it("MOVE 6 — a tick that clears the FOCUSED tile alert hands focus back to the control", async () => {
    // ⚠ DC-1, and the sixth move the deck's five did not own. Without it the
    // panel drops focus to <body> about five seconds after EVERY refused claim,
    // with no user action at all — F57's shipped MAJOR verbatim, and the fourth
    // time this repo would ship that bug class.
    //
    // MUTATION: delete the reclaim branch — focus is on <body> five seconds
    // after the refusal.
    getFloor.mockResolvedValue(floor([room()]));
    claimRoom.mockRejectedValue(new ApiError(409, "ROOM_OCCUPIED", "taken"));
    mount();
    await screen.findByText("חדר 1");

    const control = screen.getByRole("button", { name: "תפיסת החדר — חדר 1" });
    control.focus();
    fireEvent.click(control);
    await waitFor(() => expect(document.activeElement).toBe(screen.getByRole("alert")));

    // The next tick keeps the alert's promise and unmounts the focused node.
    await advance(POLL_INTERVAL_MS);
    await waitFor(() => expect(screen.queryByRole("alert")).toBeNull());

    expect(document.activeElement).not.toBe(document.body);
    expect(document.activeElement).toHaveAccessibleName("תפיסת החדר — חדר 1");
  });

  it("MOVE 6 — falls back to the heading when that tile's control is gone too", async () => {
    getFloor.mockResolvedValue(floor([room()]));
    claimRoom.mockRejectedValue(new ApiError(409, "ROOM_OCCUPIED", "taken"));
    mount();
    await screen.findByText("חדר 1");

    const control = screen.getByRole("button", { name: "תפיסת החדר — חדר 1" });
    control.focus();
    fireEvent.click(control);
    await waitFor(() => expect(document.activeElement).toBe(screen.getByRole("alert")));

    // The room is taken out of service in the same tick: no claim control left.
    getFloor.mockResolvedValue(floor([room({ is_active: false })]));
    await advance(POLL_INTERVAL_MS);

    await waitFor(() => expect(screen.queryByRole("alert")).toBeNull());
    expect(document.activeElement).toBe(
      screen.getByRole("heading", { level: 3, name: "חדרי מדידה" }),
    );
  });

  it("the pause control is still the FIRST focusable thing, ahead of every room", async () => {
    // A 2.2.2 mechanism placed after the content it governs is reachable only
    // by walking the list that is repainting under the walk — and it now
    // governs TWO repainting regions.
    getFloor.mockResolvedValue(floor([room(), room({ id: ROOM_B, label: "הבמה" })]));
    const { container } = mount();
    await screen.findByText("הבמה");

    const buttons = Array.from(container.querySelectorAll("button"));
    expect(buttons[0]).toHaveAccessibleName("השהיה — עדכון הצוות");
  });
});

// --- the ugly edges ----------------------------------------------------------

describe("the edges a 295px tile has to survive", () => {
  it("renders twenty rooms and truncates NOTHING", async () => {
    // A panel that abbreviates «חדר המדידה הגדול» and «חדר המדידה הגדול השני»
    // makes two rooms look like one, which is the exact failure this feature
    // exists to remove.
    const long = "מיכל בת אברהם כהן לוי רוזנברג מן ההר הגבוה ליד הים";
    const many = Array.from({ length: 20 }, (_, index) =>
      room({
        id: `99999999-0000-0000-0000-0000000000${String(index).padStart(2, "0")}`,
        label: `חדר ${index + 1}`,
        assignment: index === 3 ? assignment({ client_label: long }) : null,
      }),
    );
    getFloor.mockResolvedValue(floor(many));
    const { container } = mount();
    await screen.findByText("חדר 20");

    expect(document.querySelectorAll("[data-room-id]")).toHaveLength(20);
    expect(screen.getByText(long)).toBeInTheDocument();
    // No ellipsis and no truncation utility anywhere in the panel.
    expect(container.innerHTML).not.toMatch(/truncate|text-ellipsis|line-clamp/);
  });

  it("gives the long client row, the holder-gone sentence and the dress name break-words", async () => {
    // DC-7's two 295px gaps. The dress row is the worse one: `flex items-center
    // justify-between gap-3` with a <span> carrying no min-w-0 cannot shrink,
    // so a long dress name pushes «הסרה» out of a 295px tile.
    getFloor.mockResolvedValue(
      floor([
        room({
          assignment: assignment({
            staff_display_name: null,
            staff_role: null,
            dresses: [
              { id: BINDING_ID, dress_id: "d1", dress_name: "ורוניק", dress_size: null },
            ],
          }),
        }),
      ]),
    );
    mount();
    await screen.findByText("מיכל");

    expect(screen.getByText("מיכל").closest("p")).toHaveClass("break-words");
    expect(screen.getByText("אשת הצוות שתפסה את החדר כבר לא ברשימה.")).toHaveClass(
      "break-words",
    );
    const dressCell = screen.getByText("ורוניק").closest("span");
    expect(dressCell).toHaveClass("min-w-0");
    expect(dressCell).toHaveClass("break-words");
  });
});

// --- accessibility -----------------------------------------------------------

describe("accessibility", () => {
  it("starts every accessible name with its visible label (WCAG 2.5.3)", async () => {
    getFloor.mockResolvedValue(
      floor([
        room({
          assignment: assignment({
            dresses: [{ id: BINDING_ID, dress_id: "d1", dress_name: "ורוניק", dress_size: null }],
          }),
        }),
      ]),
    );
    mount();
    await screen.findByText("דנה כהן");

    for (const [visible, accessible] of [
      ["שחרור", "שחרור — חדר 1"],
      ["העברה לעמיתה", "העברה לעמיתה — חדר 1"],
      ["הוספת שמלה", "הוספת שמלה — חדר 1"],
      ["הסרה", "הסרה — ורוניק"],
    ]) {
      const control = screen.getByRole("button", { name: accessible });
      expect(control).toHaveTextContent(visible);
      expect(accessible.startsWith(visible)).toBe(true);
    }
  });

  it("puts the room in the client picker's VISIBLE label, so 2.5.3 holds by construction", async () => {
    // Four <select>s all labelled «לקוחה» is a screen-reader dead end at exactly
    // the moment the panel is busy — and an aria-label would override a
    // correctly wired <label htmlFor>.
    listFloorClients.mockResolvedValue({
      clients: [{ booking_id: BOOKING_ID, client_label: "מיכל", starts_at: NOW }],
      truncated: false,
    });
    getFloor.mockResolvedValue(floor([room()]));
    mount();
    await screen.findByText("חדר 1");

    const picker = await screen.findByRole("combobox");
    expect(picker).toHaveAccessibleName("לקוחה — חדר 1");
    expect(picker).toHaveClass("min-h-11");
  });

  it("passes axe with zero violations across all four tile states", async () => {
    // ⚠ EXPLICITLY NOT SUFFICIENT. axe cannot see a focus move that never
    // happened — three shipped instances in this repo — and it has NO rule for
    // SC 2.2.2. The focus block above and F57's shipped pause assertions are
    // the only coverage of either.
    listFloorClients.mockResolvedValue({
      clients: [{ booking_id: BOOKING_ID, client_label: "מיכל", starts_at: NOW }],
      truncated: true,
    });
    getFloor.mockResolvedValue(
      floor([
        room(),
        room({
          id: ROOM_B,
          label: "הבמה",
          assignment: assignment({
            dresses: [{ id: BINDING_ID, dress_id: "d1", dress_name: "ורוניק", dress_size: "38" }],
          }),
        }),
        room({ id: "77777777-0000-0000-0000-000000000007", label: "חדר 3", is_active: false }),
        room({
          id: "88888888-0000-0000-0000-000000000008",
          label: "חדר 4",
          assignment: assignment({ staff_display_name: null, staff_role: null, client_label: null }),
        }),
      ]),
    );
    const { container } = mount();
    await screen.findByText("חדר 4");

    const results = await run(container);
    expect(results.violations).toEqual([]);
  });

  it("passes axe on the empty state and on a refused claim", async () => {
    getFloor.mockResolvedValue(floor([]));
    const empty = mount();
    await screen.findByText("עדיין לא הוגדרו חדרי מדידה");
    expect((await run(empty.container)).violations).toEqual([]);
    empty.unmount();

    getFloor.mockResolvedValue(floor([room()]));
    claimRoom.mockRejectedValue(
      new ApiError(409, "ROOM_OCCUPIED", "taken", { staff_display_name: "דנה כהן" }),
    );
    const { container } = mount();
    await screen.findByText("חדר 1");
    fireEvent.click(screen.getByRole("button", { name: "תפיסת החדר — חדר 1" }));
    await screen.findByRole("alert");

    expect((await run(container)).violations).toEqual([]);
  });
});

// --- review round 1 ----------------------------------------------------------

describe("two mutations in flight at once, and the pick that outlives its list", () => {
  it("does not let a SECOND tile's response discard the FIRST tile's patch", async () => {
    // ⚠ `busy` is per room (`busyIds.includes(room.id)`) and `mutate` tracks a
    // COUNTER, so two tiles can be in flight together by design — and the loop
    // issues no tick meanwhile, so the only thing that can move `rooms`
    // underneath a handler is the other handler. Claim room 1 + release room 2
    // is server-legal (one staffer, one room; the release is somebody else's
    // assignment, which an owner may end).
    //
    // MUTATION: rebuild the list from the captured `rooms` prop instead of the
    // latest value and room 1 renders «פנוי» with a live claim control while
    // the server has it claimed.
    const occupied = room({ id: ROOM_B, label: "הבמה", assignment: assignment() });
    getFloor.mockResolvedValue(floor([room(), occupied]));
    let settleClaim: (value: Room) => void = () => {};
    let settleRelease: (value: Room) => void = () => {};
    claimRoom.mockReturnValue(
      new Promise<Room>((resolve) => {
        settleClaim = resolve;
      }),
    );
    releaseAssignment.mockReturnValue(
      new Promise<Room>((resolve) => {
        settleRelease = resolve;
      }),
    );
    mount();
    await screen.findByText("הבמה");

    fireEvent.click(screen.getByRole("button", { name: "תפיסת החדר — חדר 1" }));
    fireEvent.click(screen.getByRole("button", { name: "שחרור — הבמה" }));
    expect(claimRoom).toHaveBeenCalledTimes(1);
    expect(releaseAssignment).toHaveBeenCalledTimes(1);

    await act(async () => {
      settleClaim(room({ assignment: assignment({ staff_user_id: SELF_ID }) }));
    });
    await waitFor(() => expect(within(tile(ROOM_A)).getByText("תפוס")).toBeInTheDocument());
    await act(async () => {
      settleRelease(room({ id: ROOM_B, label: "הבמה" }));
    });

    await waitFor(() => expect(within(tile(ROOM_B)).getByText("פנוי")).toBeInTheDocument());
    // The claim's own row is still the truth for its tile.
    expect(within(tile(ROOM_A)).getByText("תפוס")).toBeInTheDocument();
    expect(within(tile(ROOM_A)).queryByRole("button", { name: "תפיסת החדר — חדר 1" })).toBeNull();
  });

  it("never sends a booking the client list no longer carries", async () => {
    // The picker is gone from the screen but `clientPick` is not: nothing
    // clears it, so the sent value has to follow the LIST rather than the map.
    //
    // MUTATION: read `clientPick[room.id]` unconditionally and the claim binds
    // a customer the screen does not show as selected.
    listFloorClients.mockResolvedValue({
      clients: [{ booking_id: BOOKING_ID, client_label: "מיכל", starts_at: NOW }],
      truncated: false,
    });
    getFloor.mockResolvedValue(floor([room(), room({ id: ROOM_B, label: "הבמה" })]));
    claimRoom.mockResolvedValue(room({ id: ROOM_B, label: "הבמה", assignment: assignment() }));
    mount();
    await screen.findByText("הבמה");
    await waitFor(() => expect(screen.getAllByRole("combobox")).toHaveLength(2));

    fireEvent.change(within(tile(ROOM_A)).getByRole("combobox"), {
      target: { value: BOOKING_ID },
    });
    // מיכל leaves the day's arrivals — an owner undoing her check-in from
    // another device — and the next claim's refetch answers without her.
    listFloorClients.mockResolvedValue({ clients: [], truncated: false });
    fireEvent.click(screen.getByRole("button", { name: "תפיסת החדר — הבמה" }));
    await waitFor(() => expect(screen.queryByRole("combobox")).toBeNull());

    fireEvent.click(screen.getByRole("button", { name: "תפיסת החדר — חדר 1" }));

    await waitFor(() => expect(claimRoom).toHaveBeenCalledTimes(2));
    expect(claimRoom).toHaveBeenLastCalledWith(ROOM_A, {});
  });

  it("clears the pick after a successful claim, so the ONE-TAP path stays anonymous", async () => {
    // copy.md §4: «ללא לקוחה» is always selected on mount and that is the
    // one-tap path. A pick that survives the claim it was made for rebinds the
    // PREVIOUS bride to the next fitting in that room, with no error anywhere.
    //
    // MUTATION: leave `clientPick` alone on success and the second claim posts
    // מיכל's booking again.
    listFloorClients.mockResolvedValue({
      clients: [{ booking_id: BOOKING_ID, client_label: "מיכל", starts_at: NOW }],
      truncated: false,
    });
    getFloor.mockResolvedValue(floor([room()]));
    claimRoom.mockResolvedValue(room({ assignment: assignment({ staff_user_id: SELF_ID }) }));
    releaseAssignment.mockResolvedValue(room());
    mount();
    await screen.findByText("חדר 1");
    await waitFor(() => expect(screen.getByRole("combobox")).toBeInTheDocument());

    fireEvent.change(screen.getByRole("combobox"), { target: { value: BOOKING_ID } });
    fireEvent.click(screen.getByRole("button", { name: "תפיסת החדר — חדר 1" }));
    await waitFor(() => expect(claimRoom).toHaveBeenCalledWith(ROOM_A, { booking_id: BOOKING_ID }));

    fireEvent.click(await screen.findByRole("button", { name: "שחרור — חדר 1" }));
    const picker = await screen.findByRole("combobox");
    expect((picker as HTMLSelectElement).value).toBe("");

    fireEvent.click(screen.getByRole("button", { name: "תפיסת החדר — חדר 1" }));
    await waitFor(() => expect(claimRoom).toHaveBeenCalledTimes(2));
    expect(claimRoom).toHaveBeenLastCalledWith(ROOM_A, {});
  });

  it("names the CLIENT, not the room, when the claim's 404 is about the booking", async () => {
    // `FloorService.claim` raises DomainNotFoundError("booking") when the picked
    // booking is cancelled, un-checked-in or outside today's Jerusalem window,
    // and the envelope carries the same NOT_FOUND body as a missing room — so
    // «החדר כבר לא זמין» is rendered beside a tile that still says «פנוי» and
    // still offers the claim. The message must name the thing she can act on.
    //
    // MUTATION: map every claim 404 to the room's sentence and this reddens.
    listFloorClients.mockResolvedValue({
      clients: [{ booking_id: BOOKING_ID, client_label: "מיכל", starts_at: NOW }],
      truncated: false,
    });
    getFloor.mockResolvedValue(floor([room()]));
    claimRoom.mockRejectedValue(new ApiError(404, "NOT_FOUND", "gone"));
    mount();
    await screen.findByText("חדר 1");
    await waitFor(() => expect(screen.getByRole("combobox")).toBeInTheDocument());

    fireEvent.change(screen.getByRole("combobox"), { target: { value: BOOKING_ID } });
    fireEvent.click(screen.getByRole("button", { name: "תפיסת החדר — חדר 1" }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("הלקוחה שנבחרה כבר לא ברשימת ההגעות של היום.");
    expect(alert.textContent).not.toContain("החדר כבר לא זמין");
    // …and the screen REPAIRS itself rather than promising a repair: the pick is
    // dropped and the list re-read, so the retry is the anonymous claim.
    await waitFor(() => expect(listFloorClients).toHaveBeenCalledTimes(2));
    expect((screen.getByRole("combobox") as HTMLSelectElement).value).toBe("");
  });

  it("still names the ROOM when the claim carried no booking at all", async () => {
    // The room sentence is not deleted — it is narrowed to the claims that
    // cannot be about a booking.
    getFloor.mockResolvedValue(floor([room()]));
    claimRoom.mockRejectedValue(new ApiError(404, "NOT_FOUND", "gone"));
    mount();
    await screen.findByText("חדר 1");

    fireEvent.click(screen.getByRole("button", { name: "תפיסת החדר — חדר 1" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "החדר כבר לא זמין. הרשימה תתוקן בעדכון הבא.",
    );
  });
});

// --- F58: «קחי את הבאה», the tile's second ending act ------------------------

describe("take-next on the tile", () => {
  it("renders FIRST in the action row, and only on a free ACTIVE tile", async () => {
    // §3.1: both acts END the tile's state and serve two different populations,
    // so neither is demoted to `ghost` — ORDER carries the hierarchy, and at 375
    // the first on the wrapped line is the one a thumb reaches first.
    getFloor.mockResolvedValue(
      floor(
        [
          room({ id: ROOM_A }),
          room({ id: ROOM_B, label: "הבמה", is_active: false }),
          room({
            id: "77777777-0000-0000-0000-000000000007",
            label: "חדר 3",
            assignment: assignment(),
          }),
        ],
        [staff()],
        [waiting()],
      ),
    );
    mount();
    await screen.findByText("הבמה");

    const free = within(tile(ROOM_A)).getAllByRole("button");
    expect(free[0]).toHaveAccessibleName("קחי את הבאה בתור — חדר 1");
    expect(free[0]).toHaveTextContent("קחי את הבאה");
    expect(free[1]).toHaveAccessibleName("תפיסת החדר — חדר 1");

    // An out-of-service tile offers neither act, and an occupied one is not
    // free to seat anybody.
    expect(within(tile(ROOM_B)).queryByRole("button", { name: /קחי את הבאה/ })).toBeNull();
    expect(
      within(tile("77777777-0000-0000-0000-000000000007")).queryByRole("button", {
        name: /קחי את הבאה/,
      }),
    ).toBeNull();
  });

  it("REMOVES the control when the queue empties, rather than refusing the tap", async () => {
    // §3.1. QUEUE_EMPTY therefore fires only on a STALE tile — the last woman
    // left between the render and the tap — and the next tick takes the control
    // away entirely.
    getFloor.mockResolvedValue(floor([room()], [staff()], [waiting()]));
    mount();
    await screen.findByRole("button", { name: "קחי את הבאה בתור — חדר 1" });

    getFloor.mockResolvedValue(floor([room()]));
    await advance(POLL_INTERVAL_MS);

    await waitFor(() =>
      expect(screen.queryByRole("button", { name: /קחי את הבאה/ })).toBeNull(),
    );
    // …and the OTHER ending act is untouched: the queue emptying says nothing
    // about the arrivals list.
    expect(screen.getByRole("button", { name: "תפיסת החדר — חדר 1" })).toBeInTheDocument();
  });

  it("dispatches the head of the queue: the tile fills, the ROW leaves, one paint", async () => {
    // §3.2. A client that patched the tile from the response and waited up to
    // five seconds for the row to leave would render the same woman as
    // in-service AND waiting.
    //
    // MUTATION: drop the waitlist half of `onDispatch` — the row survives the
    // dispatch and this reddens.
    getFloor.mockResolvedValue(floor([room()], [staff()], [waiting()]));
    takeNext.mockResolvedValue(
      dispatched(
        room({
          assignment: assignment({ staff_user_id: SELF_ID, client_label: "נועה בר" }),
        }),
      ),
    );
    mount();
    await screen.findByText("נועה בר");

    fireEvent.click(screen.getByRole("button", { name: "קחי את הבאה בתור — חדר 1" }));

    // `{}` IS the one-tap take-next on herself: the acting identity is the
    // session cookie and the QUEUE chooses the customer.
    await waitFor(() => expect(takeNext).toHaveBeenCalledWith(ROOM_A, {}));
    await waitFor(() => expect(within(tile(ROOM_A)).getByText("תפוס")).toBeInTheDocument());
    expect(screen.queryByRole("button", { name: /דלגי/ })).toBeNull();
    expect(screen.getByText("אין ממתינות בתור")).toBeInTheDocument();
  });

  it("names the ROOM in the cue and NEVER the walk-in", async () => {
    // §11.2, and it is sharper here than on a claim: her ROW LEAVES, so a cue
    // naming her would be the only place her name survives after she has gone —
    // in a persistent region on a five-role screen.
    //
    // MUTATION: interpolate `entry.name` into the cue and this reddens twice.
    getFloor.mockResolvedValue(floor([room()], [staff()], [waiting()]));
    takeNext.mockResolvedValue(
      dispatched(room({ assignment: assignment({ client_label: "נועה בר" }) })),
    );
    mount();
    await screen.findByText("נועה בר");

    fireEvent.click(screen.getByRole("button", { name: "קחי את הבאה בתור — חדר 1" }));

    await waitFor(() =>
      expect(screen.getByTestId("floor-cue")).toHaveTextContent("הלקוחה שובצה: חדר 1."),
    );
    expect(screen.getByTestId("floor-cue").textContent).not.toContain("נועה בר");
  });

  it("A31b — QUEUE_EMPTY is a NOTICE about an empty queue, not the outage sentence", async () => {
    // §3.4. Without the branch it takes describe()'s fall-through and tells a
    // manager whose queue is simply empty that the STAFF LIST failed to load,
    // in the muted outage register — the exact failure the error code is bought
    // to avoid, delivered in the wrong colour on top.
    //
    // MUTATION: delete the QUEUE_EMPTY branch from describe().
    getFloor.mockResolvedValue(floor([room()], [staff()], [waiting()]));
    takeNext.mockRejectedValue(new ApiError(409, "QUEUE_EMPTY", "empty"));
    mount();
    await screen.findByText("נועה בר");

    fireEvent.click(screen.getByRole("button", { name: "קחי את הבאה בתור — חדר 1" }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("אין ממתינות בתור.");
    expect(alert.textContent).not.toContain("לא הצלחנו לטעון");
    // The NOTICE register, and neither register is red.
    expect(alert.className).toContain("text-warning-text");
    expect(alert.className).not.toContain("text-ink-muted");
    expect(alert.className).not.toContain("text-danger");
    // MOVE 1: focus is inside the alert. Waited for rather than asserted
    // synchronously — findByRole resolves on the node being in the DOM and the
    // effect that focuses it runs after that (LOOP-STATE's rule: fix the wait,
    // never raise the timeout).
    await waitFor(() => expect(document.activeElement).toBe(alert));
  });

  it("a LOST RACE leaves the queue exactly where it was", async () => {
    // §3.3, item 2, and the only thing on this screen the CUSTOMER can feel: a
    // refused take-next must roll the ticket back, so the woman at position 1 is
    // still at position 1 with her wait clock unbroken. If this panel ever shows
    // her gone after a refusal, the transaction design failed.
    getFloor.mockResolvedValue(floor([room()], [staff()], [waiting()]));
    takeNext.mockRejectedValue(
      new ApiError(409, "ROOM_OCCUPIED", "taken", { staff_display_name: "דנה כהן" }),
    );
    mount();
    await screen.findByText("נועה בר");

    fireEvent.click(screen.getByRole("button", { name: "קחי את הבאה בתור — חדר 1" }));

    // The SHIPPED F36 sentence, reused rather than re-keyed.
    expect(await screen.findByRole("alert")).toHaveTextContent("דנה כהן כבר בחדר הזה.");
    expect(screen.getByText("נועה בר")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "קראי — נועה בר" })).toBeInTheDocument();
    // Nothing was achieved, so the persistent region says nothing.
    expect(screen.getByTestId("floor-cue")).toHaveTextContent("");
  });

  it("DC-3 — a take-next STAFF_OCCUPIED speaks about HER, in the second person", async () => {
    // The dispatch routes send no staff_user_id, so the target IS the acting
    // manager and F36's third-person «היא כבר בחדר אחר» tells her about herself.
    // A SECOND sentence rather than an edit: the shipped value is asserted
    // verbatim in three shipped test files.
    //
    // MUTATION: drop the `target === "queue"` fork and this reddens.
    getFloor.mockResolvedValue(floor([room()], [staff()], [waiting()]));
    takeNext.mockRejectedValue(
      new ApiError(409, "STAFF_OCCUPIED", "hers", { room_label: "הבמה" }),
    );
    mount();
    await screen.findByText("נועה בר");

    fireEvent.click(screen.getByRole("button", { name: "קחי את הבאה בתור — חדר 1" }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("את כבר בחדר אחר: הבמה.");
    expect(alert.textContent).not.toContain("היא כבר");
    expect(alert.querySelector("bdi")).toHaveTextContent("הבמה");
  });

  it("DC-3 — …and the details-less twin drops the room, not the person", async () => {
    getFloor.mockResolvedValue(floor([room()], [staff()], [waiting()]));
    takeNext.mockRejectedValue(new ApiError(409, "STAFF_OCCUPIED", "hers"));
    mount();
    await screen.findByText("נועה בר");

    fireEvent.click(screen.getByRole("button", { name: "קחי את הבאה בתור — חדר 1" }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("את כבר בחדר אחר.");
    expect(alert.textContent).not.toContain("היא כבר");
  });

  it("gives a take-next 404 the ROOM's sentence, never the assignment's", async () => {
    // take-next raises DomainNotFoundError("fitting_room") and nothing else, so
    // «הלקוחה כבר לא בחדר» would be a sentence about a fitting that never
    // started. The `queue` target rides the room's 404 branch, paused twin
    // included.
    getFloor.mockResolvedValue(floor([room()], [staff()], [waiting()]));
    takeNext.mockRejectedValue(new ApiError(404, "NOT_FOUND", "gone"));
    mount();
    await screen.findByText("נועה בר");

    fireEvent.click(screen.getByRole("button", { name: "קחי את הבאה בתור — חדר 1" }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("החדר כבר לא זמין. הרשימה תתוקן בעדכון הבא.");
    expect(alert.textContent).not.toContain("הלקוחה כבר לא בחדר");
  });

  it("DC-2(a) — the tile's focus slot belongs to «קחי את הבאה» whenever it renders", async () => {
    // controlRefs is ONE slot per room and React runs ref callbacks in TREE
    // order, so an unguarded claim callback runs LAST and silently wins it —
    // and ~5s later MOVE 6 hands focus to «תפיסת החדר», a control she never
    // touched. The slot belongs to the tile's FIRST control.
    //
    // MUTATION: remove the `waitlistCount === 0` guard from the claim button's
    // ref callback — focus lands on «תפיסת החדר — חדר 1» and this reddens.
    getFloor.mockResolvedValue(floor([room()], [staff()], [waiting()]));
    takeNext.mockRejectedValue(new ApiError(409, "ROOM_OCCUPIED", "taken"));
    mount();
    await screen.findByText("נועה בר");

    const control = screen.getByRole("button", { name: "קחי את הבאה בתור — חדר 1" });
    control.focus();
    fireEvent.click(control);
    await waitFor(() => expect(document.activeElement).toBe(screen.getByRole("alert")));

    // The next tick keeps the alert's promise and unmounts the focused node —
    // with the queue still populated, so both controls are still rendered.
    await advance(POLL_INTERVAL_MS);
    await waitFor(() => expect(screen.queryByRole("alert")).toBeNull());

    expect(document.activeElement).not.toBe(document.body);
    expect(document.activeElement).toHaveAccessibleName("קחי את הבאה בתור — חדר 1");
  });

  it("DC-2(b) — only the control she pressed spins, and BOTH are disabled", async () => {
    // `disabled` is shared because one tile can serve one act at a time;
    // `loading` is not, because two spinners on one tile say two requests are
    // in flight.
    //
    // MUTATION: give both controls `loading={busy}` — the claim reports
    // aria-busy and this reddens.
    getFloor.mockResolvedValue(floor([room()], [staff()], [waiting()]));
    takeNext.mockReturnValue(new Promise<DispatchResult>(() => {}));
    mount();
    await screen.findByText("נועה בר");

    const control = screen.getByRole("button", { name: "קחי את הבאה בתור — חדר 1" });
    fireEvent.click(control);

    const claimControl = screen.getByRole("button", { name: "תפיסת החדר — חדר 1" });
    await waitFor(() => expect(control).toBeDisabled());
    expect(claimControl).toBeDisabled();
    expect(control).toHaveAttribute("aria-busy", "true");
    expect(claimControl).not.toHaveAttribute("aria-busy");
  });

  it("…and the same rule the other way round when the CLAIM is the act", async () => {
    getFloor.mockResolvedValue(floor([room()], [staff()], [waiting()]));
    claimRoom.mockReturnValue(new Promise<Room>(() => {}));
    mount();
    await screen.findByText("נועה בר");

    const claimControl = screen.getByRole("button", { name: "תפיסת החדר — חדר 1" });
    fireEvent.click(claimControl);

    const control = screen.getByRole("button", { name: "קחי את הבאה בתור — חדר 1" });
    await waitFor(() => expect(claimControl).toBeDisabled());
    expect(control).toBeDisabled();
    expect(claimControl).toHaveAttribute("aria-busy", "true");
    expect(control).not.toHaveAttribute("aria-busy");
  });

  it("passes axe on a free tile carrying both ending acts", async () => {
    // New markup on a shipped tile: a second `secondary` in the action row, and
    // the waitlist panel below it. axe has no rule for either of the two things
    // this task actually turns on (a focus move, a register), so this row is
    // necessary and explicitly not sufficient.
    getFloor.mockResolvedValue(floor([room()], [staff()], [waiting()]));
    const { container } = mount();
    await screen.findByText("נועה בר");

    const results = await run(container);
    expect(results.violations).toEqual([]);
  });
});
