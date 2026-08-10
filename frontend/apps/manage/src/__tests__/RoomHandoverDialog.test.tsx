import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { run } from "axe-core";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import "../i18n";
import type { FloorResponse, Room, RoomAssignment, StaffCard } from "../api";
import { FloorPanel } from "../components/FloorPanel";
import { SosProvider } from "../lib/sos";
import { POLL_INTERVAL_MS } from "../lib/usePoll";

// ⚠ F37 INFRASTRUCTURE, NOT AN EXPECTATION. FloorPanel now renders SosCentre,
// which reads useSos() — and that hook THROWS outside the provider, deliberately
// (loud beats inert for an emergency channel). So the render helper gains the
// provider and the api mock gains getSos, exactly as F36 added listFloorClients
// here. Every assertion below is untouched.
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
      getSos: vi.fn(),
      raiseSos: vi.fn(),
      acceptSos: vi.fn(),
      resolveSos: vi.fn(),
      cancelSos: vi.fn(),
      claimRoom: vi.fn(),
      releaseAssignment: vi.fn(),
      removeAssignmentDress: vi.fn(),
      createRoom: vi.fn(),
      updateRoom: vi.fn(),
      deleteRoom: vi.fn(),
      listFloorDresses: vi.fn(),
      addAssignmentDress: vi.fn(),
      handoverAssignment: vi.fn(),
    },
  };
});

const { api, ApiError } = await import("../api");
const getFloor = vi.mocked(api.getFloor);
const listFloorClients = vi.mocked(api.listFloorClients);
const getSos = vi.mocked(api.getSos);
const listFloorDresses = vi.mocked(api.listFloorDresses);
const handoverAssignment = vi.mocked(api.handoverAssignment);

const NOW = "2026-08-04T11:07:00Z";
const BREAK_BEGAN = "2026-08-04T08:20:00Z";
const SELF_ID = "11111111-1111-1111-1111-111111111111";
const DANA = "22222222-2222-2222-2222-222222222222";
const NOA = "33333333-3333-3333-3333-333333333333";
const RUTI = "44444444-4444-4444-4444-444444444444";
const ROOM_A = "aaaaaaaa-0000-0000-0000-000000000001";
const ASSIGNMENT_ID = "cccccccc-0000-0000-0000-000000000003";

function card(overrides: Partial<StaffCard> = {}): StaffCard {
  return {
    id: NOA,
    display_name: "נועה לוי",
    role: "seamstress",
    status: "available",
    break_started_at: null,
    occupancy: null,
    // F38's two, defaulted to the no-photo state most of a boutique is in.
    photo_url: null,
    photo_confirmed_at: null,
    ...overrides,
  };
}

const ME = card({ id: SELF_ID, display_name: "רותם", role: "owner" });
const HOLDER = card({ id: DANA, display_name: "דנה כהן", status: "occupied" });

function assignment(overrides: Partial<RoomAssignment> = {}): RoomAssignment {
  return {
    id: ASSIGNMENT_ID,
    staff_user_id: DANA,
    staff_display_name: "דנה כהן",
    staff_role: "seamstress",
    client_label: "מיכל",
    booking_id: null,
    assigned_at: NOW,
    dresses: [],
    ...overrides,
  };
}

function room(overrides: Partial<Room> = {}): Room {
  return {
    id: ROOM_A,
    label: "חדר 2",
    sort_order: 0,
    is_active: true,
    assignment: assignment(),
    ...overrides,
  };
}

function floor(rooms: Room[], cards: StaffCard[] = [ME, HOLDER, card()]): FloorResponse {
  return { staff: cards, rooms, server_now: NOW, waitlist: { entries: [], truncated: false } };
}

function mount(role = "owner") {
  return render(
    <SosProvider>
      <FloorPanel selfId={SELF_ID} role={role} />
    </SosProvider>,
  );
}

function dialogs(): HTMLDialogElement[] {
  return screen.queryAllByRole("dialog", { hidden: true }) as HTMLDialogElement[];
}

function open(): HTMLDialogElement {
  const found = dialogs().find((node) => node.open);
  if (found === undefined) {
    throw new Error("no open dialog");
  }
  return found;
}

async function openHandover() {
  fireEvent.click(screen.getByRole("button", { name: "העברה לעמיתה — חדר 2" }));
  await waitFor(() => expect(open()).toHaveTextContent("העברת החדר"));
  return open();
}

beforeEach(() => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  vi.setSystemTime(new Date(NOW));
  getFloor.mockReset();
  listFloorClients.mockReset();
  listFloorDresses.mockReset();
  handoverAssignment.mockReset();
  listFloorClients.mockResolvedValue({ clients: [], truncated: false });
  getSos.mockReset();
  getSos.mockResolvedValue({ alerts: [], server_now: NOW , unread_notifications: 0 });
  listFloorDresses.mockResolvedValue({ dresses: [], truncated: false });
  getFloor.mockResolvedValue(floor([room()]));
});

afterEach(() => {
  vi.useRealTimers();
});

async function advance(ms: number) {
  await act(async () => {
    vi.advanceTimersByTime(ms);
  });
}

// --- the colleague list ------------------------------------------------------

describe("the list is built from the payload the poll already carries", () => {
  it("makes NO second request for it", async () => {
    mount();
    await screen.findByText("חדר 2");
    const before = getFloor.mock.calls.length;

    await openHandover();

    expect(getFloor.mock.calls.length).toBe(before);
    expect(within(open()).getByLabelText("העברה אל")).toBeInTheDocument();
  });

  it("excludes the current holder and every OCCUPIED colleague", async () => {
    // The 409 STAFF_OCCUPIED is usually PREVENTED rather than explained.
    getFloor.mockResolvedValue(
      floor([room()], [ME, HOLDER, card(), card({ id: RUTI, display_name: "רותי", status: "occupied" })]),
    );
    mount();
    await screen.findByText("חדר 2");
    const modal = await openHandover();

    const options = within(within(modal).getByLabelText("העברה אל"))
      .getAllByRole("option")
      .map((node) => node.textContent);
    expect(options).toEqual(["רותם", "נועה לוי"]);
  });

  it("KEEPS a colleague on a break, and her option says so", async () => {
    // She is not excluded: the server accepts the handover and the indexes do
    // not forbid it, so hiding her would be the client asserting a rule the
    // server does not have. The realistic case is a staffer who forgot to end a
    // break — which is exactly what the corrected boolean makes visible.
    getFloor.mockResolvedValue(
      floor([room()], [ME, HOLDER, card({ status: "break", break_started_at: BREAK_BEGAN })]),
    );
    mount();
    await screen.findByText("חדר 2");
    const modal = await openHandover();

    const options = within(within(modal).getByLabelText("העברה אל"))
      .getAllByRole("option")
      .map((node) => node.textContent);
    expect(options).toEqual(["רותם", "נועה לוי — בהפסקה"]);
  });

  it("still OPENS when nobody is free, explains, and offers no confirm", async () => {
    // A trigger that does nothing is worse than a dialog that explains.
    getFloor.mockResolvedValue(floor([room()], [HOLDER]));
    mount();
    await screen.findByText("חדר 2");
    const modal = await openHandover();

    expect(within(modal).getByText("אין עכשיו עמיתה פנויה לקבל את החדר.")).toBeInTheDocument();
    expect(within(modal).queryByLabelText("העברה אל")).toBeNull();
    expect(within(modal).queryByRole("button", { name: "העברה" })).toBeNull();
    expect(within(modal).getByRole("button", { name: "ביטול" })).toBeInTheDocument();
  });
});

// --- the handover ------------------------------------------------------------

describe("the handover itself", () => {
  it("hands the room over, patches the tile and announces the RECEIVING colleague", async () => {
    // Names her rather than the room: what needs confirming is who has it now,
    // and the room is not in doubt — she opened the dialog from its tile.
    handoverAssignment.mockResolvedValue(
      room({ assignment: assignment({ staff_user_id: NOA, staff_display_name: "נועה לוי" }) }),
    );
    mount();
    await screen.findByText("חדר 2");
    const modal = await openHandover();

    fireEvent.change(within(modal).getByLabelText("העברה אל"), { target: { value: NOA } });
    fireEvent.click(within(modal).getByRole("button", { name: "העברה" }));

    await waitFor(() =>
      expect(handoverAssignment).toHaveBeenCalledWith(ASSIGNMENT_ID, { staff_user_id: NOA }),
    );
    expect(screen.getByTestId("floor-cue")).toHaveTextContent("החדר הועבר אל נועה לוי.");
    await waitFor(() => expect(dialogs().some((node) => node.open)).toBe(false));
    // The tile patched from the response — the assignment id is stable across a
    // handover, only the holder moved.
    const tile = document.querySelector(`[data-room-id="${ROOM_A}"]`) as HTMLElement;
    expect(within(tile).getByText("נועה לוי")).toBeInTheDocument();
    expect(within(tile).queryByText("דנה כהן")).toBeNull();
  });

  it("KEEPS the dialog open on the residual 409 and names her current room", async () => {
    // The race the exclusion cannot close: the receiving colleague took a room
    // between the tick and the confirm. The dialog stays so a shift manager can
    // pick somebody else without reopening it.
    handoverAssignment.mockRejectedValue(
      new ApiError(409, "STAFF_OCCUPIED", "hers", { room_label: "הבמה" }),
    );
    mount();
    await screen.findByText("חדר 2");
    const modal = await openHandover();

    fireEvent.click(within(modal).getByRole("button", { name: "העברה" }));

    const alert = await within(modal).findByRole("alert");
    expect(alert).toHaveTextContent("היא כבר בחדר אחר: הבמה.");
    expect(alert).toHaveClass("text-warning-text");
    expect(modal.open).toBe(true);
    expect(within(modal).getByRole("button", { name: "העברה" })).toBeEnabled();
    expect(alert.querySelector("bdi")).toHaveTextContent("הבמה");
  });

  it("CLOSES on a 404 and hands the tile the assignment-gone sentence, focus in the alert", async () => {
    handoverAssignment.mockRejectedValue(new ApiError(404, "NOT_FOUND", "gone"));
    mount();
    await screen.findByText("חדר 2");
    const modal = await openHandover();

    fireEvent.click(within(modal).getByRole("button", { name: "העברה" }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("הלקוחה כבר לא בחדר.");
    await waitFor(() => expect(document.activeElement).toBe(alert));
    expect(dialogs().some((node) => node.open)).toBe(false);
  });
});

// --- focus -------------------------------------------------------------------

// The plain "returns to «העברה לעמיתה» on cancel" case USED TO LIVE HERE and was
// REMOVED — it could not fail. jsdom 29's HTMLDialogElementImpl is an empty subclass
// (9 lines, no showModal), so `test/setup.ts` installs a stub that sets `open = true`
// and moves no focus; the test focused the trigger itself before opening, and the
// stub never took it away. Its own comment claimed "jsdom implements the <dialog>
// close focusing steps" — that was simply false.
// The rule IS proven in `frontend/e2e/dialog-focus.spec.ts` against mutations M1 and
// M3b, in a browser that implements <dialog>. `Modal` is shared, so that platform
// restore path is this dialog's too.
// MOVE 5 below is the half the platform cannot serve, and it reds when deleted.
describe("focus — the release the platform cannot serve", () => {
  it("MOVE 5 — a tick that releases the assignment closes it, never onto <body>", async () => {
    mount();
    await screen.findByText("חדר 2");
    const modal = await openHandover();
    within(modal).getByRole("button", { name: "העברה" }).focus();

    getFloor.mockResolvedValue(floor([room({ assignment: null })]));
    await advance(POLL_INTERVAL_MS);

    await waitFor(() => expect(dialogs().some((node) => node.open)).toBe(false));
    expect(document.activeElement).not.toBe(document.body);
    expect(document.activeElement).toBe(
      screen.getByRole("heading", { level: 3, name: "חדרי מדידה" }),
    );
  });

  it("passes axe with the dialog open", async () => {
    mount();
    await screen.findByText("חדר 2");
    await openHandover();

    expect((await run(document.body)).violations).toEqual([]);
  });
});
