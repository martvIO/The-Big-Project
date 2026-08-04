import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { run } from "axe-core";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import "../i18n";
import type { FloorResponse, Room, RoomAssignment, StaffCard } from "../api";
import { FloorPanel } from "../components/FloorPanel";
import { SosProvider } from "../lib/sos";
import { POLL_INTERVAL_MS } from "../lib/usePoll";

// Mounted THROUGH FloorPanel → RoomsPanel. Move 5 is the reason: the poll is
// only SUPPRESSED while a mutation is in flight, never while a dialog is merely
// open, so a colleague releasing the assignment unmounts the tile and the dialog
// under the user's hands with focus inside — F57's own shipped MAJOR reproduced
// one level deeper, and axe sees none of it. A direct render could not produce
// it at all.
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
    },
  };
});

const { api, ApiError } = await import("../api");
const getFloor = vi.mocked(api.getFloor);
const listFloorClients = vi.mocked(api.listFloorClients);
const getSos = vi.mocked(api.getSos);
const listFloorDresses = vi.mocked(api.listFloorDresses);
const addAssignmentDress = vi.mocked(api.addAssignmentDress);

const NOW = "2026-08-04T11:07:00Z";
const SELF_ID = "11111111-1111-1111-1111-111111111111";
const ROOM_A = "aaaaaaaa-0000-0000-0000-000000000001";
const ASSIGNMENT_ID = "cccccccc-0000-0000-0000-000000000003";

function staff(): StaffCard {
  return {
    id: SELF_ID,
    display_name: "רותם",
    role: "owner",
    status: "available",
    break_started_at: null,
    occupancy: null,
  };
}

function assignment(overrides: Partial<RoomAssignment> = {}): RoomAssignment {
  return {
    id: ASSIGNMENT_ID,
    staff_user_id: SELF_ID,
    staff_display_name: "רותם",
    staff_role: "owner",
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

function floor(rooms: Room[]): FloorResponse {
  return { staff: [staff()], rooms, server_now: NOW, waitlist: { entries: [], truncated: false } };
}

function mount() {
  return render(
    <SosProvider>
      <FloorPanel selfId={SELF_ID} role="owner" />
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

async function openDress() {
  fireEvent.click(screen.getByRole("button", { name: "הוספת שמלה — חדר 2" }));
  await waitFor(() => expect(open()).toHaveTextContent("הוספת שמלה — חדר 2"));
  return open();
}

beforeEach(() => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  vi.setSystemTime(new Date(NOW));
  getFloor.mockReset();
  listFloorClients.mockReset();
  listFloorDresses.mockReset();
  addAssignmentDress.mockReset();
  listFloorClients.mockResolvedValue({ clients: [], truncated: false });
  getSos.mockReset();
  getSos.mockResolvedValue({ alerts: [], server_now: NOW });
  listFloorDresses.mockResolvedValue({
    dresses: [
      { id: "d1", name: "ורוניק", sizes: ["38", "40"] },
      { id: "d2", name: "סברינה", sizes: [] },
    ],
    truncated: false,
  });
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

// --- the catalog read --------------------------------------------------------

describe("one read per open, and never on the tick", () => {
  it("fetches the catalog when the dialog opens and NOT before", async () => {
    mount();
    await screen.findByText("חדר 2");
    expect(listFloorDresses).not.toHaveBeenCalled();

    await openDress();
    expect(listFloorDresses).toHaveBeenCalledTimes(1);

    // Three ticks with the dialog open: the poll never touches this list.
    await advance(POLL_INTERVAL_MS);
    await advance(POLL_INTERVAL_MS);
    await advance(POLL_INTERVAL_MS);
    expect(listFloorDresses).toHaveBeenCalledTimes(1);
  });

  it("filters CLIENT-SIDE, with no second request", async () => {
    // No ?q=, no debounce, no server-side search — the whole list is already
    // here and a second round trip would buy nothing.
    mount();
    await screen.findByText("חדר 2");
    const modal = await openDress();

    fireEvent.change(within(modal).getByLabelText("חיפוש שמלה"), { target: { value: "ורו" } });

    const picker = within(modal).getByLabelText("שמלה");
    expect(within(picker).getAllByRole("option").map((o) => o.textContent)).toEqual(["ורוניק"]);
    expect(listFloorDresses).toHaveBeenCalledTimes(1);
  });
});

// --- the four list states ----------------------------------------------------

describe("every list state, not just the populated one", () => {
  it("removes both pickers and the confirm when the filter matches nothing", async () => {
    // A <select> with zero options is a dead control that looks live.
    mount();
    await screen.findByText("חדר 2");
    const modal = await openDress();

    fireEvent.change(within(modal).getByLabelText("חיפוש שמלה"), { target: { value: "זזז" } });

    expect(within(modal).getByText("אין שמלה שמתאימה לחיפוש.")).toBeInTheDocument();
    expect(within(modal).queryByLabelText("שמלה")).toBeNull();
    expect(within(modal).queryByLabelText("מידה")).toBeNull();
    expect(within(modal).queryByRole("button", { name: "הוספה" })).toBeNull();
  });

  it("says the catalog is empty and offers NO CTA", async () => {
    // Three of the five roles cannot reach «שמלות» at all, so pointing them at
    // a door that answers 403 is the trap §2.2 exists to avoid.
    listFloorDresses.mockResolvedValue({ dresses: [], truncated: false });
    mount();
    await screen.findByText("חדר 2");
    const modal = await openDress();

    await waitFor(() =>
      expect(within(modal).getByText("אין עדיין שמלות בקטלוג.")).toBeInTheDocument(),
    );
    expect(within(modal).queryByRole("link")).toBeNull();
    expect(within(modal).queryByRole("button", { name: "הוספה" })).toBeNull();
  });

  it("names no count and no limit on a truncated catalog, and points at the FILTER", async () => {
    // A narrowing of D16, which pointed at «שמלות» — a section three of the
    // five roles cannot open. The remedy that is in the dialog with her is the
    // search box.
    listFloorDresses.mockResolvedValue({
      dresses: [{ id: "d1", name: "ורוניק", sizes: [] }],
      truncated: true,
    });
    mount();
    await screen.findByText("חדר 2");
    const modal = await openDress();

    const line = await within(modal).findByText(/הרשימה חלקית/);
    expect(line).toHaveTextContent("החיפוש");
    expect(line.textContent).not.toMatch(/\d/);
  });

  it("hides the size picker entirely for a dress with no sizes at all", async () => {
    mount();
    await screen.findByText("חדר 2");
    const modal = await openDress();

    fireEvent.change(within(modal).getByLabelText("שמלה"), { target: { value: "d2" } });

    expect(within(modal).queryByLabelText("מידה")).toBeNull();
    expect(within(modal).getByRole("button", { name: "הוספה" })).toBeInTheDocument();
  });
});

// --- the add -----------------------------------------------------------------

describe("the add", () => {
  it("sends the chosen dress AND size, patches the tile and announces the DRESS", async () => {
    addAssignmentDress.mockResolvedValue(
      room({
        assignment: assignment({
          dresses: [{ id: "b1", dress_id: "d1", dress_name: "ורוניק", dress_size: "40" }],
        }),
      }),
    );
    mount();
    await screen.findByText("חדר 2");
    const modal = await openDress();

    fireEvent.change(within(modal).getByLabelText("מידה"), { target: { value: "40" } });
    fireEvent.click(within(modal).getByRole("button", { name: "הוספה" }));

    await waitFor(() =>
      expect(addAssignmentDress).toHaveBeenCalledWith(ASSIGNMENT_ID, {
        dress_id: "d1",
        size_label: "40",
      }),
    );
    expect(screen.getByTestId("floor-cue")).toHaveTextContent("השמלה נוספה לחדר: ורוניק.");
    // …and the tile patched from the response, so the binding is on the tile as
    // well as in the cue.
    const tile = document.querySelector(`[data-room-id="${ROOM_A}"]`) as HTMLElement;
    expect(within(tile).getByText("ורוניק")).toBeInTheDocument();
    expect(within(tile).getByText("שמלות בחדר")).toBeInTheDocument();
  });

  it("binds a NULL size for a sample gown carried in before a size is chosen", async () => {
    // «ללא מידה» is always first and always the default: D4's stated ordinary
    // case, and dress_size is nullable for exactly it.
    addAssignmentDress.mockResolvedValue(room());
    mount();
    await screen.findByText("חדר 2");
    const modal = await openDress();

    expect(within(within(modal).getByLabelText("מידה")).getAllByRole("option")[0]).toHaveTextContent(
      "ללא מידה",
    );
    fireEvent.click(within(modal).getByRole("button", { name: "הוספה" }));

    await waitFor(() =>
      expect(addAssignmentDress).toHaveBeenCalledWith(ASSIGNMENT_ID, { dress_id: "d1" }),
    );
  });
});

// --- moves 4 and 5, each with its named mutation -----------------------------

describe("focus — the two contracts, and axe sees neither", () => {
  it("MOVE 4 — closing returns focus to the tile's «הוספת שמלה» trigger", async () => {
    // ⚠ THIS ONE ASSERTS THE OUTCOME, NOT OUR MECHANISM, and it is labelled so
    // rather than left to look stronger than it is: jsdom implements the
    // <dialog> close focusing steps, so deleting the [openDialog] restore effect
    // leaves this GREEN — verified by running that mutation. The effect earns
    // its keep on the path the platform CANNOT serve, where the trigger has gone
    // with its assignment; the non-vacuous tests for it are the MOVE 5 pair and
    // the registry's DC-10 case, and all three red when it is deleted.
    mount();
    await screen.findByText("חדר 2");
    const trigger = screen.getByRole("button", { name: "הוספת שמלה — חדר 2" });
    trigger.focus();
    const modal = await openDress();

    fireEvent.click(within(modal).getByRole("button", { name: "ביטול" }));

    await waitFor(() => expect(trigger).toHaveFocus());
  });

  it("MOVE 4 COLLISION — a 404 add closes the dialog and lands focus IN THE TILE'S ALERT", async () => {
    // ⚠ Move 1 must beat the native <dialog>'s own focus return, which fires
    // second and would otherwise win. The sentence is the ASSIGNMENT's, not the
    // room's: «החדר כבר לא זמין» would be actively misleading when the room is
    // fine and the fitting simply ended.
    //
    // MUTATION: let the native return win (drop the tile-alert focus) and this
    // lands on the trigger instead of the alert.
    addAssignmentDress.mockRejectedValue(new ApiError(404, "NOT_FOUND", "gone"));
    mount();
    await screen.findByText("חדר 2");
    const modal = await openDress();

    fireEvent.click(within(modal).getByRole("button", { name: "הוספה" }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("הלקוחה כבר לא בחדר. הרשימה תתוקן בעדכון הבא.");
    await waitFor(() => expect(document.activeElement).toBe(alert));
    expect(dialogs().some((node) => node.open)).toBe(false);
  });

  it("MOVE 5 — a poll tick that releases the assignment closes the dialog, never onto <body>", async () => {
    // ⚠ F57's shipped MAJOR one level deeper: the poll is only suppressed while
    // a mutation is in flight, so it keeps ticking with a dialog merely OPEN,
    // and a colleague releasing the room unmounts the tile and the dialog under
    // her hands with focus inside.
    //
    // MUTATION: remove the open-dialog reconciliation — the dialog stays open
    // over a tile that no longer has an assignment.
    mount();
    await screen.findByText("חדר 2");
    const modal = await openDress();
    within(modal).getByRole("button", { name: "הוספה" }).focus();

    getFloor.mockResolvedValue(floor([room({ assignment: null })]));
    await advance(POLL_INTERVAL_MS);

    await waitFor(() => expect(dialogs().some((node) => node.open)).toBe(false));
    expect(document.activeElement).not.toBe(document.body);
    // The «הוספת שמלה» trigger went with the assignment, so the rescue target
    // is the rooms heading.
    expect(document.activeElement).toBe(
      screen.getByRole("heading", { level: 3, name: "חדרי מדידה" }),
    );
  });

  it("passes axe with the dialog open", async () => {
    // ⚠ NOT SUFFICIENT: axe cannot see either move above, and it has no rule
    // for SC 2.2.2 either.
    mount();
    await screen.findByText("חדר 2");
    await openDress();

    expect((await run(document.body)).violations).toEqual([]);
  });
});

// --- review round 1 ----------------------------------------------------------

describe("the size follows the gown the picker actually shows", () => {
  it("drops a size the newly derived gown does not come in", async () => {
    // ⚠ `chosen` is DERIVED from `matches` while `size` is stored state, reset
    // only by the gown picker's own onChange. Typing in the filter re-derives
    // `chosen` with no onChange at all, so the size survives onto a different
    // gown — and the server stores `size_label` verbatim as the permanent
    // snapshot with no lookup against dress_variants, so the binding row reads
    // «סברינה · 40» for a gown that has no sizes at all.
    //
    // MUTATION: pass the stored `size` to onAdd and the posted body carries
    // "40" instead of no size.
    addAssignmentDress.mockResolvedValue(
      room({
        assignment: assignment({
          dresses: [
            { id: "b1", dress_id: "d2", dress_name: "סברינה", dress_size: null },
          ],
        }),
      }),
    );
    mount();
    await screen.findByText("חדר 2");
    const modal = await openDress();

    fireEvent.change(within(modal).getByLabelText("מידה"), { target: { value: "40" } });
    // ורוניק drops out; סברינה becomes the derived gown and has no sizes at all,
    // so the size picker unmounts while its state survives.
    fireEvent.change(within(modal).getByLabelText("חיפוש שמלה"), { target: { value: "סבר" } });
    expect(within(modal).queryByLabelText("מידה")).toBeNull();

    fireEvent.click(within(modal).getByRole("button", { name: "הוספה" }));

    await waitFor(() => expect(addAssignmentDress).toHaveBeenCalledTimes(1));
    expect(addAssignmentDress).toHaveBeenCalledWith(ASSIGNMENT_ID, { dress_id: "d2" });
  });
});
