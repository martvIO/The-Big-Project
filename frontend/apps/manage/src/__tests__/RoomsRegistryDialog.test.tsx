import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { run } from "axe-core";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import "../i18n";
import type { FloorResponse, Room, RoomAssignment, StaffCard } from "../api";
import { FloorPanel } from "../components/FloorPanel";
import { MAX_SORT_ORDER } from "../validation";
import { POLL_INTERVAL_MS } from "../lib/usePoll";

// Mounted THROUGH FloorPanel → RoomsPanel, not in isolation: the seed-once
// contract, the focus return through the panel's own trigger and the DC-10
// fallback to the rooms h3 are all statements about what happens to this dialog
// while a five-second poll runs underneath it. A direct render would stub
// exactly the thing under test.
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
      createRoom: vi.fn(),
      updateRoom: vi.fn(),
      deleteRoom: vi.fn(),
    },
  };
});

const { api, ApiError } = await import("../api");
const getFloor = vi.mocked(api.getFloor);
const listFloorClients = vi.mocked(api.listFloorClients);
const createRoom = vi.mocked(api.createRoom);
const updateRoom = vi.mocked(api.updateRoom);
const deleteRoom = vi.mocked(api.deleteRoom);

const NOW = "2026-08-04T11:07:00Z";
const SELF_ID = "11111111-1111-1111-1111-111111111111";
const OTHER_ID = "22222222-2222-2222-2222-222222222222";
const ROOM_A = "aaaaaaaa-0000-0000-0000-000000000001";
const ROOM_B = "bbbbbbbb-0000-0000-0000-000000000002";
const NEW_ROOM = "cccccccc-0000-0000-0000-000000000003";

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

function assignment(overrides: Partial<RoomAssignment> = {}): RoomAssignment {
  return {
    id: "dddddddd-0000-0000-0000-000000000004",
    staff_user_id: OTHER_ID,
    staff_display_name: "דנה כהן",
    staff_role: "seamstress",
    client_label: "מיכל",
    booking_id: null,
    assigned_at: NOW,
    dresses: [],
    ...overrides,
  };
}

function floor(rooms: Room[]): FloorResponse {
  return { staff: [staff()], rooms, server_now: NOW };
}

function mount(role = "owner") {
  return render(<FloorPanel selfId={SELF_ID} role={role} />);
}

// jsdom keeps a top-layer <dialog> out of the accessibility tree the way a
// browser does, so every query into one goes through `hidden: true` — the shape
// StaffSection.test.tsx already uses for the shipped confirm.
function dialogs(): HTMLDialogElement[] {
  return screen.getAllByRole("dialog", { hidden: true }) as HTMLDialogElement[];
}

function registry(): HTMLDialogElement {
  return dialogs()[0];
}

async function openRegistry() {
  fireEvent.click(screen.getByRole("button", { name: "ניהול חדרים" }));
  await waitFor(() => expect(registry().open).toBe(true));
  return registry();
}

function rowFor(label: string): HTMLElement {
  const input = within(registry()).getByDisplayValue(label);
  const row = input.closest("[data-registry-row]");
  if (row === null) {
    throw new Error(`no registry row for ${label}`);
  }
  return row as HTMLElement;
}

beforeEach(() => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  vi.setSystemTime(new Date(NOW));
  getFloor.mockReset();
  listFloorClients.mockReset();
  createRoom.mockReset();
  updateRoom.mockReset();
  deleteRoom.mockReset();
  listFloorClients.mockResolvedValue({ clients: [], truncated: false });
  getFloor.mockResolvedValue(floor([room(), room({ id: ROOM_B, label: "הבמה", sort_order: 2 })]));
});

afterEach(() => {
  vi.useRealTimers();
});

async function advance(ms: number) {
  await act(async () => {
    vi.advanceTimersByTime(ms);
  });
}

// --- opening, and the two doors to one dialog --------------------------------

describe("the registry opens from whichever trigger exists", () => {
  it("lists every room in the server's order, with the add row LAST", async () => {
    mount();
    await screen.findByText("הבמה");

    const modal = await openRegistry();
    expect(modal).toHaveTextContent("חדרי המדידה של הבוטיק");
    const labels = within(modal)
      .getAllByLabelText("שם החדר")
      .map((node) => (node as HTMLInputElement).value);
    // The add row is last, because a new room defaults to sort_order 0 and the
    // tiebreak is created_at — which is where the list will show it.
    expect(labels).toEqual(["חדר 1", "הבמה", ""]);
  });

  it("opens from the EMPTY state's CTA too — two labels, one dialog", async () => {
    // A brand-new boutique's very first registry session, and the case §1.2
    // names as the one that needs the focus fallback.
    getFloor.mockResolvedValue(floor([]));
    mount();
    await screen.findByText("עדיין לא הוגדרו חדרי מדידה");

    fireEvent.click(screen.getByRole("button", { name: "הוספת חדר" }));
    await waitFor(() => expect(registry().open).toBe(true));
    expect(registry()).toHaveTextContent("חדרי המדידה של הבוטיק");
  });
});

// --- add, rename, reorder, deactivate ----------------------------------------

describe("the four registry verbs", () => {
  it("adds a room, announces it INSIDE the dialog, and shows it on the panel behind", async () => {
    createRoom.mockResolvedValue(room({ id: NEW_ROOM, label: "חדר 3" }));
    mount();
    await screen.findByText("הבמה");
    const modal = await openRegistry();

    const addRow = within(modal).getByTestId("registry-add");
    fireEvent.change(within(addRow).getByLabelText("שם החדר"), { target: { value: "חדר 3" } });
    fireEvent.click(within(addRow).getByRole("button", { name: "הוספה" }));

    await waitFor(() => expect(createRoom).toHaveBeenCalledWith({ label: "חדר 3" }));
    // The dialog's OWN role="status", not the panel's cue region: a live region
    // outside an open modal is not reliably announced while the dialog holds
    // the accessibility tree (deck F-8).
    await waitFor(() =>
      expect(within(modal).getByTestId("registry-cue")).toHaveTextContent("החדר נוסף."),
    );
    expect(screen.getByTestId("floor-cue")).toHaveTextContent("");
    // …and the panel behind the dialog has the new tile.
    expect(document.querySelectorAll("[data-room-id]")).toHaveLength(3);
  });

  it("renames a row and confirms it with the console's SHIPPED save phrasing", async () => {
    // `common.saved` reused rather than a fourth rooms.savedCue — the console
    // has rendered that sentence on every save screen since F8.
    updateRoom.mockResolvedValue(room({ label: "חדר המדידה הגדול" }));
    mount();
    await screen.findByText("הבמה");
    const modal = await openRegistry();

    const row = rowFor("חדר 1");
    fireEvent.change(within(row).getByLabelText("שם החדר"), {
      target: { value: "חדר המדידה הגדול" },
    });
    fireEvent.click(within(row).getByRole("button", { name: "שמירה" }));

    await waitFor(() =>
      expect(updateRoom).toHaveBeenCalledWith(ROOM_A, { label: "חדר המדידה הגדול", sort_order: 0 }),
    );
    expect(within(modal).getByTestId("registry-cue")).toHaveTextContent("נשמר לפני רגע");
  });

  it("reorders through a LABELLED number input a keyboard can reach and operate", async () => {
    // ⚠ MUTATION: swap this for a drag handle and the assertion below reddens
    // — while axe stays green, which is the whole point. Drag's most common
    // implementation is a WCAG 2.1.1 keyboard failure axe cannot see.
    updateRoom.mockResolvedValue(room({ sort_order: -1 }));
    mount();
    await screen.findByText("הבמה");
    const modal = await openRegistry();

    const order = within(rowFor("חדר 1")).getByLabelText("סדר תצוגה");
    expect(order).toHaveAttribute("type", "number");
    expect(order).not.toHaveAttribute("disabled");
    // Negatives are legal and useful: they move a row to the front without
    // renumbering the rest, which is why D1 chose the symmetric bound.
    fireEvent.change(order, { target: { value: "-1" } });
    fireEvent.click(within(rowFor("חדר 1")).getByRole("button", { name: "שמירה" }));

    await waitFor(() =>
      expect(updateRoom).toHaveBeenCalledWith(ROOM_A, { label: "חדר 1", sort_order: -1 }),
    );
    expect(within(modal).queryByRole("button", { name: /גרירה|הזזה/ })).toBeNull();
  });

  it("deactivates IMMEDIATELY, with no save step, and evicts nobody", async () => {
    // is_active and deleted_at are two different facts: this one means «the
    // mirror is broken, do not send anyone in there today» and leaves the room
    // on the panel, greyed, with the bride still in it.
    getFloor.mockResolvedValue(floor([room({ assignment: assignment() })]));
    updateRoom.mockResolvedValue(room({ is_active: false, assignment: assignment() }));
    mount();
    await screen.findByText("דנה כהן");
    await openRegistry();

    fireEvent.click(within(rowFor("חדר 1")).getByRole("switch", { name: "פעיל" }));

    await waitFor(() => expect(updateRoom).toHaveBeenCalledWith(ROOM_A, { is_active: false }));
    // Nobody was evicted: the assignment is still on the tile behind.
    expect(screen.getByText("דנה כהן")).toBeInTheDocument();
  });

  it("keeps «שמירה» always enabled — a clean row is a PATCH that changes nothing", async () => {
    updateRoom.mockResolvedValue(room());
    mount();
    await screen.findByText("הבמה");
    await openRegistry();

    const save = within(rowFor("חדר 1")).getByRole("button", { name: "שמירה" });
    expect(save).toBeEnabled();
    fireEvent.click(save);
    await waitFor(() => expect(updateRoom).toHaveBeenCalled());
  });
});

// --- validation, field-local ------------------------------------------------

describe("validation lands in the field she must fix", () => {
  it("refuses a stripped-empty label without asking the server", async () => {
    mount();
    await screen.findByText("הבמה");
    await openRegistry();

    const row = rowFor("חדר 1");
    fireEvent.change(within(row).getByLabelText("שם החדר"), { target: { value: "   " } });
    fireEvent.click(within(row).getByRole("button", { name: "שמירה" }));

    expect(within(row).getByRole("alert")).toHaveTextContent("צריך למלא שם לחדר.");
    expect(within(row).getByLabelText("שם החדר")).toHaveAttribute("aria-invalid", "true");
    expect(updateRoom).not.toHaveBeenCalled();
  });

  it("refuses a sort order outside the MIRRORED bound, and names no number", async () => {
    mount();
    await screen.findByText("הבמה");
    await openRegistry();

    const row = rowFor("חדר 1");
    fireEvent.change(within(row).getByLabelText("סדר תצוגה"), {
      target: { value: String(MAX_SORT_ORDER + 1) },
    });
    fireEvent.click(within(row).getByRole("button", { name: "שמירה" }));

    const alert = within(rowFor("חדר 1")).getByRole("alert");
    expect(alert).toHaveTextContent("סדר התצוגה מחוץ לטווח.");
    expect(alert.textContent).not.toMatch(/\d/);
    expect(updateRoom).not.toHaveBeenCalled();
  });

  it("caps the label input at the mirrored length rather than letting her overrun it", async () => {
    mount();
    await screen.findByText("הבמה");
    await openRegistry();

    expect(within(rowFor("חדר 1")).getByLabelText("שם החדר")).toHaveAttribute("maxLength", "40");
  });

  it("refuses an empty ADD without a request", async () => {
    mount();
    await screen.findByText("הבמה");
    const modal = await openRegistry();

    const addRow = within(modal).getByTestId("registry-add");
    fireEvent.click(within(addRow).getByRole("button", { name: "הוספה" }));

    expect(within(addRow).getByRole("alert")).toHaveTextContent("צריך למלא שם לחדר.");
    expect(createRoom).not.toHaveBeenCalled();
  });
});

// --- delete: the nested confirm, and the one place a registry act meets D3 ---

describe("delete — a nested Modal, and the 409 that has to name a person", () => {
  async function openConfirm(label: string) {
    fireEvent.click(within(rowFor(label)).getByRole("button", { name: "מחיקה" }));
    await waitFor(() => expect(dialogs()).toHaveLength(2));
    return dialogs()[1];
  }

  it("names the room as its OWN ELEMENT, never interpolated into the title", async () => {
    // Modal.title is typed `string`, so a room label inside it could not be
    // bidi-isolated at all — and it would sit mid-string with a «?» after it,
    // the one position where a Latin-script label reorders visibly.
    mount();
    await screen.findByText("הבמה");
    await openRegistry();

    const confirm = await openConfirm("הבמה");
    expect(confirm).toHaveTextContent("למחוק את החדר מרשימת החדרים?");
    expect(within(confirm).getByText("הבמה").tagName).toBe("BDI");
    // The body states the one rule she can hit, so the 409 below is expected
    // rather than a surprise.
    expect(confirm).toHaveTextContent("אי אפשר למחוק חדר שיש בו לקוחה עכשיו.");
  });

  it("deletes on confirm, announces it, and drops the tile behind", async () => {
    deleteRoom.mockResolvedValue({ ok: true });
    mount();
    await screen.findByText("הבמה");
    const modal = await openRegistry();

    const confirm = await openConfirm("הבמה");
    fireEvent.click(within(confirm).getByRole("button", { name: "מחיקה" }));

    await waitFor(() => expect(deleteRoom).toHaveBeenCalledWith(ROOM_B));
    await waitFor(() =>
      expect(within(modal).getByTestId("registry-cue")).toHaveTextContent("החדר נמחק."),
    );
    expect(document.querySelectorAll("[data-room-id]")).toHaveLength(1);
  });

  it("cancelling deletes nothing and closes only the topmost dialog", async () => {
    mount();
    await screen.findByText("הבמה");
    await openRegistry();

    const confirm = await openConfirm("הבמה");
    fireEvent.click(within(confirm).getByRole("button", { name: "ביטול" }));

    await waitFor(() => expect(confirm.open).toBe(false));
    expect(deleteRoom).not.toHaveBeenCalled();
    expect(registry().open).toBe(true);
  });

  it("NAMES the occupant on a 409 and KEEPS the confirm so a retry costs one tap", async () => {
    // ⚠ The one place a registry action meets the concurrency design, and it
    // needs its own sentence: rooms.error.ROOM_OCCUPIED is written for a claim
    // («כבר בחדר הזה») and reads as a non-sequitur as a reason a DELETE failed.
    deleteRoom.mockRejectedValue(
      new ApiError(409, "ROOM_OCCUPIED", "occupied", { staff_display_name: "דנה כהן" }),
    );
    mount();
    await screen.findByText("הבמה");
    await openRegistry();

    const confirm = await openConfirm("הבמה");
    fireEvent.click(within(confirm).getByRole("button", { name: "מחיקה" }));

    await waitFor(() =>
      expect(within(confirm).getByRole("alert")).toHaveTextContent(
        "דנה כהן נמצאת בחדר עכשיו. אפשר למחוק אותו אחרי שהיא תצא.",
      ),
    );
    // Retained: closing would make her walk the whole path again two minutes
    // later. And never red — nothing that went wrong here is her fault.
    expect(confirm.open).toBe(true);
    expect(within(confirm).getByRole("button", { name: "מחיקה" })).toBeEnabled();
    expect(within(confirm).getByRole("alert")).toHaveClass("text-warning-text");
  });

  it("says the room is taken without naming anybody when the holder is a GHOST", async () => {
    // ⚠ Reachable here by a shape the claim's version is not: the delete's
    // occupancy check and its occupant read sit under one per-room FOR UPDATE,
    // so the "released in between" race cannot happen — but a holder
    // soft-deleted mid-fitting still resolves to no name (D11).
    deleteRoom.mockRejectedValue(new ApiError(409, "ROOM_OCCUPIED", "occupied"));
    mount();
    await screen.findByText("הבמה");
    await openRegistry();

    const confirm = await openConfirm("הבמה");
    fireEvent.click(within(confirm).getByRole("button", { name: "מחיקה" }));

    await waitFor(() =>
      expect(within(confirm).getByRole("alert")).toHaveTextContent(
        "החדר תפוס עכשיו. אפשר למחוק אותו אחרי שיתפנה.",
      ),
    );
    // It says nothing about a customer: at this point the panel knows only that
    // the room is not free.
    expect(within(confirm).getByRole("alert").textContent).not.toContain("לקוחה");
  });

  it("closes the confirm and re-seeds when the row has ALREADY vanished", async () => {
    deleteRoom.mockRejectedValue(new ApiError(404, "NOT_FOUND", "gone"));
    mount();
    await screen.findByText("הבמה");
    const modal = await openRegistry();

    const confirm = await openConfirm("הבמה");
    fireEvent.click(within(confirm).getByRole("button", { name: "מחיקה" }));

    await waitFor(() => expect(confirm.open).toBe(false));
    expect(within(modal).getByTestId("registry-cue")).toHaveTextContent("החדר כבר לא זמין.");
  });
});

// --- AC25: the seed-once contract -------------------------------------------

describe("AC25 — the dialog lives inside a component that repaints every five seconds", () => {
  it("leaves a DIRTY input alone when a tick lands underneath it", async () => {
    // ⚠ MUTATION: re-read the rows from `rooms` on every render and this
    // reddens. holdRef does not help — it consumes ONE tick on pointerdown and
    // typing fires no pointer events — and this feature's "patch from the
    // server's row, never optimistic" discipline makes a re-read a RESET rather
    // than a merge.
    mount();
    await screen.findByText("הבמה");
    const modal = await openRegistry();

    fireEvent.change(within(rowFor("חדר 1")).getByLabelText("שם החדר"), {
      target: { value: "חדר 4" },
    });

    getFloor.mockResolvedValue(
      floor([room({ label: "חדר 1" }), room({ id: ROOM_B, label: "הבמה", sort_order: 2 })]),
    );
    await advance(POLL_INTERVAL_MS);
    await advance(POLL_INTERVAL_MS);

    expect(within(modal).getAllByLabelText("שם החדר")[0]).toHaveValue("חדר 4");
  });

  it("re-seeds on the NEXT open, so a room changed underneath shows the truth", async () => {
    mount();
    await screen.findByText("הבמה");
    const modal = await openRegistry();
    fireEvent.change(within(rowFor("חדר 1")).getByLabelText("שם החדר"), {
      target: { value: "חדר 4" },
    });
    fireEvent.click(within(modal).getByRole("button", { name: "סגירה" }));
    await waitFor(() => expect(registry().open).toBe(false));

    getFloor.mockResolvedValue(floor([room({ label: "חדר 9" })]));
    await advance(POLL_INTERVAL_MS);
    await waitFor(() => expect(screen.getByText("חדר 9")).toBeInTheDocument());

    await openRegistry();
    expect(within(registry()).getAllByLabelText("שם החדר")[0]).toHaveValue("חדר 9");
  });

  it("never reaches for poll.pause() — the panel keeps its own beat and says so", async () => {
    // The pause control's accessible name would otherwise announce a state the
    // owner did not choose (F57's D12), and a panel that goes quiet without
    // saying so is what F34's whole freshness contract exists to prevent.
    mount();
    await screen.findByText("הבמה");
    await openRegistry();
    const before = getFloor.mock.calls.length;

    await advance(POLL_INTERVAL_MS);

    expect(getFloor.mock.calls.length).toBeGreaterThan(before);
    expect(screen.getByRole("button", { name: "השהיה — עדכון הצוות" })).toBeInTheDocument();
  });
});

// --- focus: the return, and DC-10's fallback --------------------------------

describe("focus — the return is ours, not the platform's", () => {
  it("returns focus to «ניהול חדרים» on close", async () => {
    mount();
    await screen.findByText("הבמה");
    const trigger = screen.getByRole("button", { name: "ניהול חדרים" });
    trigger.focus();
    await openRegistry();

    fireEvent.click(within(registry()).getByRole("button", { name: "סגירה" }));

    await waitFor(() => expect(trigger).toHaveFocus());
  });

  it("DC-10 — returns focus to the rooms HEADING when the last room is gone", async () => {
    // ⚠ The FIRST registry session in every boutique's life runs in reverse of
    // this, and the same rescue is what saves it: she opens from the EmptyState
    // CTA, adds a room, closes — and the trigger she came from no longer exists
    // because the panel now renders the heading-row one instead.
    //
    // MUTATION: always focus the trigger, and this lands on <body>.
    getFloor.mockResolvedValue(floor([room()]));
    deleteRoom.mockResolvedValue({ ok: true });
    mount();
    await screen.findByText("חדר 1");
    screen.getByRole("button", { name: "ניהול חדרים" }).focus();
    const modal = await openRegistry();

    fireEvent.click(within(rowFor("חדר 1")).getByRole("button", { name: "מחיקה" }));
    await waitFor(() => expect(dialogs()).toHaveLength(2));
    fireEvent.click(within(dialogs()[1]).getByRole("button", { name: "מחיקה" }));
    await waitFor(() => expect(deleteRoom).toHaveBeenCalled());

    fireEvent.click(within(modal).getByRole("button", { name: "סגירה" }));

    await waitFor(() => expect(screen.queryByRole("button", { name: "ניהול חדרים" })).toBeNull());
    expect(document.activeElement).not.toBe(document.body);
    expect(document.activeElement).toBe(
      screen.getByRole("heading", { level: 3, name: "חדרי מדידה" }),
    );
  });

  it("Esc dismisses rather than confirming, and hands focus back", async () => {
    // Modal's onCancel preventDefaults and calls onClose — dismiss only, never
    // a confirm, which is the shipped component's contract.
    mount();
    await screen.findByText("הבמה");
    const trigger = screen.getByRole("button", { name: "ניהול חדרים" });
    trigger.focus();
    const modal = await openRegistry();

    fireEvent(modal, new Event("cancel", { bubbles: false, cancelable: true }));

    await waitFor(() => expect(registry().open).toBe(false));
    expect(updateRoom).not.toHaveBeenCalled();
    expect(deleteRoom).not.toHaveBeenCalled();
    await waitFor(() => expect(trigger).toHaveFocus());
  });

  it("keeps the focus trap the PLATFORM's — a real top-layer dialog, not a div", async () => {
    // The whole reason P-7 chose a nested Modal over the storefront's inline
    // two-step: native <dialog> gives the trap, the Esc handling and the
    // stacking for free, and the alternative's focus test is already on the
    // known_flaky list.
    mount();
    await screen.findByText("הבמה");
    const modal = await openRegistry();

    expect(modal.tagName).toBe("DIALOG");
    expect(modal.open).toBe(true);
    fireEvent.click(within(rowFor("הבמה")).getByRole("button", { name: "מחיקה" }));
    await waitFor(() => expect(dialogs()).toHaveLength(2));
    // Two mounted at once, which Modal's own comment anticipates.
    expect(dialogs()[1].tagName).toBe("DIALOG");
    expect(dialogs()[1].open).toBe(true);
  });
});

// --- DC-9: the dense registry ------------------------------------------------

describe("DC-9 — twenty rooms", () => {
  it("renders every row, each one operable, and leans on the UA's dialog scroll", async () => {
    const many = Array.from({ length: 20 }, (_, index) =>
      room({
        id: `99999999-0000-0000-0000-0000000000${String(index).padStart(2, "0")}`,
        label: `חדר ${index + 1}`,
        sort_order: index,
      }),
    );
    getFloor.mockResolvedValue(floor(many));
    mount();
    await screen.findByText("חדר 20");
    const modal = await openRegistry();

    expect(within(modal).getAllByTestId("registry-row")).toHaveLength(20);
    // Row 18 is as reachable as row 1 — no virtualisation, no pagination, and
    // the Modal declares no max-height of its own, so the UA's
    // `dialog:modal { max-height; overflow: auto }` is what makes the list
    // scrollable. Worth an assertion rather than an assumption.
    expect(within(rowFor("חדר 18")).getByRole("button", { name: "שמירה" })).toBeEnabled();
    expect(modal.className).not.toMatch(/max-h-|overflow-/);
  });
});

// --- accessibility -----------------------------------------------------------

describe("accessibility", () => {
  it("passes axe on the registry and on its nested confirm", async () => {
    // ⚠ NOT SUFFICIENT, and the reorder control is the proof: a drag handle
    // passes axe and fails WCAG 2.1.1. The keyboard assertion above is the only
    // coverage of that.
    mount();
    await screen.findByText("הבמה");
    const { container } = { container: document.body };
    await openRegistry();
    expect((await run(container)).violations).toEqual([]);

    fireEvent.click(within(rowFor("הבמה")).getByRole("button", { name: "מחיקה" }));
    await waitFor(() => expect(dialogs()).toHaveLength(2));
    expect((await run(container)).violations).toEqual([]);
  });
});
