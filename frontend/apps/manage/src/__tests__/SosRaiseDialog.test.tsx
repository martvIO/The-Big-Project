import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { run } from "axe-core";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import "../i18n";
import type { FloorResponse, Room, RoomAssignment, SosAlert, StaffCard } from "../api";
import { FloorPanel } from "../components/FloorPanel";
import { SosProvider } from "../lib/sos";
import { MAX_SOS_NOTE_LENGTH } from "../validation";

/**
 * ⚠ THREE FOCUS MOVES INSIDE A NATIVE <dialog>, WHERE «THE BROWSER HANDLES IT»
 * IS FALSE — and the spec named none of them.
 *
 *   E  the send control is REPLACED by «הבנתי» on a rerouted raise;
 *   F  the failure alert appears after the send button's blur;
 *   G  the dialog closes and focus must return to the trigger.
 *
 * `Button` is `disabled={disabled || loading}`, so a real browser blurs the
 * focused child the instant the request starts — and a <dialog> whose focused
 * child is then REMOVED drops focus to the dialog element or to <body> depending
 * on engine. E and F are the fifth and sixth instances of the bug class this
 * repo has shipped four times, on the surface D15 declares a gate condition.
 *
 * ⚠ MOVE G IS NOT A REUSE OF RoomsPanel's SHIPPED EFFECT, and citing it would
 * ship the fifth. That effect is keyed on ROOMS PANEL's OWN `openDialog` state,
 * which never changes for a dialog `FloorPanel` owns: it would never run, the
 * native dialog's own return would have no target, and focus would drop to
 * <body> for something the user did.
 */

// ⚠ F37 INFRASTRUCTURE, NOT AN EXPECTATION. FloorPanel now renders SosCentre,
// which reads useSos() — and that hook THROWS outside the provider, deliberately.
vi.mock("../api", async () => {
  const actual = await vi.importActual<typeof import("../api")>("../api");
  return {
    ApiError: actual.ApiError,
    errorMessage: actual.errorMessage,
    FALLBACK_ERROR_MESSAGE: actual.FALLBACK_ERROR_MESSAGE,
    api: {
      getFloor: vi.fn(),
      startStaffBreak: vi.fn(),
      endStaffBreak: vi.fn(),
      listFloorClients: vi.fn(),
      listFloorDresses: vi.fn(),
      addAssignmentDress: vi.fn(),
      removeAssignmentDress: vi.fn(),
      claimRoom: vi.fn(),
      releaseAssignment: vi.fn(),
      handoverAssignment: vi.fn(),
      createRoom: vi.fn(),
      updateRoom: vi.fn(),
      deleteRoom: vi.fn(),
      getSos: vi.fn(),
      raiseSos: vi.fn(),
      acceptSos: vi.fn(),
      resolveSos: vi.fn(),
      cancelSos: vi.fn(),
    },
  };
});

const { api } = await import("../api");
const getFloor = vi.mocked(api.getFloor);
const listFloorClients = vi.mocked(api.listFloorClients);
const getSos = vi.mocked(api.getSos);
const raiseSos = vi.mocked(api.raiseSos);

const NOW = "2026-08-04T11:07:00Z";
const SELF_ID = "11111111-1111-1111-1111-111111111111";
const DANA = "22222222-2222-2222-2222-222222222222";
const NOA = "33333333-3333-3333-3333-333333333333";
const ROOM_A = "aaaaaaaa-0000-0000-0000-000000000001";
const ASSIGNMENT_ID = "cccccccc-0000-0000-0000-000000000003";
const ALERT_ID = "dddddddd-0000-0000-0000-000000000004";

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
const DANA_CARD = card({ id: DANA, display_name: "דנה כהן" });

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

function floor(rooms: Room[] = [], cards: StaffCard[] = [ME, DANA_CARD, card()]): FloorResponse {
  return {
    staff: cards,
    rooms,
    server_now: NOW,
    // F58's envelope field. Empty is what these journeys were written against.
    waitlist: { entries: [], truncated: false },
  };
}

function raised(overrides: Partial<SosAlert> = {}): SosAlert {
  return {
    id: ALERT_ID,
    status: "open",
    raised_by: SELF_ID,
    raised_by_name: "רותם",
    target_staff_user_id: null,
    target_name: null,
    room_label: "חדר 2",
    note: null,
    accepted_by: null,
    accepted_by_name: null,
    acknowledged_at: null,
    created_at: NOW,
    escalated: false,
    stalled: false,
    for_me: false,
    ...overrides,
  };
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

function openDialog(): HTMLDialogElement {
  const found = dialogs().find((node) => node.open);
  if (found === undefined) {
    throw new Error("no open dialog");
  }
  return found;
}

async function openFromCentre() {
  fireEvent.click(screen.getByRole("button", { name: "קריאה לעזרה" }));
  await waitFor(() => expect(openDialog()).toHaveTextContent("למי לקרוא"));
  return openDialog();
}

beforeEach(() => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  vi.setSystemTime(new Date(NOW));
  getFloor.mockReset();
  listFloorClients.mockReset();
  getSos.mockReset();
  raiseSos.mockReset();
  listFloorClients.mockResolvedValue({ clients: [], truncated: false });
  getSos.mockResolvedValue({ alerts: [], server_now: NOW , unread_notifications: 0 });
  getFloor.mockResolvedValue(floor());
});

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

// --- the target list ----------------------------------------------------------

describe("the target list", () => {
  it("puts «מנהלת המשמרת» first and default, excludes herself, annotates a break", async () => {
    // ⚠ The shift-manager route is the one whose audience can NEVER be empty, so
    // it is the choice a staffer under pressure never has to think about.
    // Herself is EXCLUDED because the server refuses a self-target with a 400 —
    // excluding it PREVENTS the error rather than explaining it.
    // A colleague on a break is ANNOTATED and NOT excluded: a seamstress on a
    // five-minute break is exactly who you want for a corset back.
    getFloor.mockResolvedValue(
      floor([], [ME, DANA_CARD, card({ status: "break", break_started_at: NOW })]),
    );
    mount();
    await screen.findByText("אין עכשיו קריאות פתוחות.");
    const dialog = await openFromCentre();

    const options = within(dialog)
      .getAllByRole("option")
      .map((node) => node.textContent);
    expect(options[0]).toBe("מנהלת המשמרת");
    expect(within(dialog).getByLabelText("למי לקרוא")).toHaveValue("");
    expect(options).not.toContain("רותם");
    expect(options).toContain("נועה לוי — בהפסקה");
    expect(options).toContain("דנה כהן");
  });

  it("still offers «מנהלת המשמרת» when there are no colleagues at all", async () => {
    getFloor.mockResolvedValue(floor([], [ME]));
    mount();
    await screen.findByText("אין עכשיו קריאות פתוחות.");
    const dialog = await openFromCentre();

    expect(within(dialog).getAllByRole("option")).toHaveLength(1);
    expect(within(dialog).getAllByRole("option")[0]).toHaveTextContent("מנהלת המשמרת");
  });

  it("caps the note at the mirrored server bound, so over-length is unreachable", async () => {
    mount();
    await screen.findByText("אין עכשיו קריאות פתוחות.");
    const dialog = await openFromCentre();

    expect(within(dialog).getByLabelText("מה צריך")).toHaveAttribute(
      "maxlength",
      String(MAX_SOS_NOTE_LENGTH),
    );
    // The help line matters more here than anywhere else in the console: a
    // staffer who believes the field is required will TYPE something rather
    // than tap send, and this is the one screen where two seconds is real.
    expect(dialog).toHaveTextContent("לא חובה");
  });
});

// --- the send, and the two states that keep the dialog open --------------------

describe("the send", () => {
  it("closes on an ordinary raise and cues «הקריאה נרשמה.» — never «נשלחה»", async () => {
    raiseSos.mockResolvedValue({ alert: raised(), rerouted: false });
    mount();
    await screen.findByText("אין עכשיו קריאות פתוחות.");
    const dialog = await openFromCentre();

    fireEvent.change(within(dialog).getByLabelText("מה צריך"), {
      target: { value: "צריך סיכות" },
    });
    fireEvent.click(within(dialog).getByRole("button", { name: "שליחת הקריאה" }));

    await waitFor(() => expect(dialogs().some((node) => node.open)).toBe(false));
    expect(screen.getByTestId("floor-cue")).toHaveTextContent("הקריאה נרשמה.");
    expect(raiseSos).toHaveBeenCalledWith({
      target_staff_user_id: null,
      fitting_room_assignment_id: null,
      note: "צריך סיכות",
    });
  });

  it("AC2 — a REROUTED raise KEEPS THE DIALOG OPEN with «הבנתי», and MOVE E lands on it", async () => {
    // ⚠ The ruling requires that when a named colleague is unreachable the
    // raiser is told ON SCREEN before she puts the phone down — and `rerouted`
    // is a fact about the REQUEST, so no SosCentre row can ever show it again.
    // Delivered as a transient cue at the moment a <dialog> closes and focus
    // moves, it is the classic case assistive tech drops or defers. Miss it and
    // she believes Dana was paged, Dana was never paged, and nothing on any
    // screen will ever say otherwise.
    raiseSos.mockResolvedValue({ alert: raised({ target_name: null }), rerouted: true });
    mount();
    await screen.findByText("אין עכשיו קריאות פתוחות.");
    const dialog = await openFromCentre();
    fireEvent.change(within(dialog).getByLabelText("למי לקרוא"), { target: { value: DANA } });

    const send = within(dialog).getByRole("button", { name: "שליחת הקריאה" });
    send.focus();
    fireEvent.click(send);
    // ⚠ EXPLICIT BLUR — the real browser's, which jsdom does not perform.
    send.blur();

    await waitFor(() => expect(dialog).toHaveTextContent("דנה כהן לא מחוברת עכשיו."));
    expect(dialog.open).toBe(true);
    expect(dialog).toHaveTextContent("הקריאה עברה למנהלת המשמרת.");
    const ack = within(dialog).getByRole("button", { name: "הבנתי" });
    // MOVE E: the control that had focus has just unmounted.
    //
    // ⚠ `waitFor`, NOT a bare assertion, and it is a fix for a REAL 1-in-8 flake
    // on the unmodified tree (measured, `<body>` instead of the ack). jsdom's
    // focus fixup when the focused `send` control is REMOVED does not always land
    // before React flushes the passive effect that runs MOVE E, so under load the
    // fixup can undo the move. A real browser runs that fixup synchronously
    // inside the removal steps, long before any passive effect, so this is a
    // jsdom scheduling artefact and not a product defect — `e2e/sos.spec.ts`
    // measures the same move in Chromium.
    //
    // It is NOT vacuous: delete MOVE E and focus stays on `<body>` forever, so
    // this times out and reds. Mutation-checked.
    await waitFor(() => expect(document.activeElement).toBe(ack));
    expect(within(dialog).queryByRole("button", { name: "שליחת הקריאה" })).toBeNull();

    fireEvent.click(ack);
    await waitFor(() => expect(dialogs().some((node) => node.open)).toBe(false));
  });

  it("AC2 — and the rerouted sentence is ANNOUNCED, not merely rendered", async () => {
    // ⚠ THE ONE MESSAGE THE RULING MANDATES WAS ANNOUNCED TO NOBODY. The body is
    // swapped for a bare <p>; `Modal` sets only aria-labelledby and no
    // aria-describedby, so the swapped body is not part of the dialog's
    // accessible description either; and MOVE E then moves focus to a button
    // whose entire label is «הבנתי». A blind seamstress heard exactly «הבנתי,
    // לחצן» and nothing about Dana — then acknowledged and put the phone down
    // believing Dana was paged. `rerouted` is a fact about the REQUEST (D10), so
    // no SosCentre row can ever tell her afterwards.
    //
    // Two mechanisms, because either alone is engine-dependent here: a live
    // region for the swap, and a description on the control MOVE E focuses so it
    // is read WITH the button name. The sibling failure branch one line over
    // already carries role="alert"; this branch carried nothing.
    raiseSos.mockResolvedValue({ alert: raised({ target_name: null }), rerouted: true });
    mount();
    await screen.findByText("אין עכשיו קריאות פתוחות.");
    const dialog = await openFromCentre();
    fireEvent.change(within(dialog).getByLabelText("למי לקרוא"), { target: { value: DANA } });

    fireEvent.click(within(dialog).getByRole("button", { name: "שליחת הקריאה" }));
    await waitFor(() => expect(dialog).toHaveTextContent("דנה כהן לא מחוברת עכשיו."));

    const live = within(dialog).getByRole("status");
    expect(live).toHaveTextContent("דנה כהן לא מחוברת עכשיו.");
    expect(live).toHaveTextContent("הקריאה עברה למנהלת המשמרת.");

    // …and the control MOVE E lands on carries it as its description, so it is
    // read even if the live region is preempted by the focus move.
    const ack = within(dialog).getByRole("button", { name: "הבנתי" });
    expect(ack.getAttribute("aria-describedby")).toBe(live.id);
    expect(live.id).not.toBe("");
  });

  it("AC30 — a REJECTED send keeps it open with the note preserved, and MOVE F lands on the alert", async () => {
    // A 5xx, a dropped connection, a wifi blackspot inside a curtain — the
    // single most likely real-world failure of a phone held behind a closed
    // fitting-room curtain. `FALLBACK_ERROR_MESSAGE`'s bare «נסי שוב» is the
    // wrong instruction on the one screen where «open the curtain and shout» is
    // the right one.
    raiseSos.mockRejectedValue(new Error("wifi"));
    mount();
    await screen.findByText("אין עכשיו קריאות פתוחות.");
    const dialog = await openFromCentre();
    fireEvent.change(within(dialog).getByLabelText("מה צריך"), {
      target: { value: "צריך סיכות" },
    });

    const send = within(dialog).getByRole("button", { name: "שליחת הקריאה" });
    send.focus();
    fireEvent.click(send);
    send.blur();

    await waitFor(() =>
      expect(dialog).toHaveTextContent("הקריאה לא נרשמה. נסי שוב — או קראי בקול."),
    );
    expect(dialog.open).toBe(true);
    expect(dialog).not.toHaveTextContent("אירעה שגיאה בלתי צפויה");
    // The note survives, so a retry costs one tap.
    expect(within(dialog).getByLabelText("מה צריך")).toHaveValue("צריך סיכות");
    // ⚠ MOVE F lands in a PASSIVE effect, so it is NOT flushed by the `waitFor`
    // above — that one returns the moment the alert TEXT is committed, one React
    // phase before the focus move. Asserting focus bare passes only while the
    // machine is idle enough for the effect to sneak in first; under parallel
    // load it read the send button (which jsdom leaves focused, since `blur()`
    // no-ops on the `disabled` control — the very case this guard allows) and
    // this test failed ~50% of the time. Wait for the move, do not race it.
    await waitFor(() => expect(document.activeElement).toBe(within(dialog).getByRole("alert")));
  });

  it("MOVE F's other direction — a failure landing after she tabbed back to the note leaves it alone", async () => {
    // A test that asserts «focus moved to X» cannot fail when focus is taken
    // from somewhere it should not have been, so this direction is its own
    // block: she tapped send, then went back to fix the note while the request
    // was in the air, and the 5xx must not pull her out of the field.
    let reject: (error: unknown) => void = () => {};
    raiseSos.mockReturnValue(new Promise((_resolve, r) => (reject = r)));
    mount();
    await screen.findByText("אין עכשיו קריאות פתוחות.");
    const dialog = await openFromCentre();

    const send = within(dialog).getByRole("button", { name: "שליחת הקריאה" });
    send.focus();
    fireEvent.click(send);
    send.blur();
    const note = within(dialog).getByLabelText("מה צריך");
    note.focus();

    await act(async () => {
      reject(new Error("wifi"));
      await Promise.resolve();
    });
    await waitFor(() => expect(dialog).toHaveTextContent("הקריאה לא נרשמה."));

    expect(document.activeElement).toBe(note);
  });
});

// --- AC31 / MOVE G -------------------------------------------------------------

describe("AC31 / MOVE G — the focus return runs from FloorPanel's OWN trigger ref", () => {
  it("lands on the trigger that opened it", async () => {
    mount();
    await screen.findByText("אין עכשיו קריאות פתוחות.");
    const trigger = screen.getByRole("button", { name: "קריאה לעזרה" });
    await openFromCentre();

    fireEvent.click(screen.getByRole("button", { name: "ביטול" }));
    await waitFor(() => expect(dialogs().some((node) => node.open)).toBe(false));

    expect(document.activeElement).toBe(trigger);
  });

  it("falls back to FloorPanel's own h2 when the tile was released underneath", async () => {
    // ⚠ NEVER <body>. The tile trigger's element is passed UP and held here, so
    // when a colleague releases the room mid-dialog the element is disconnected
    // and the heading actually in scope takes the focus.
    getFloor.mockResolvedValue(floor([room()]));
    mount();
    await screen.findByText("חדר 2");
    fireEvent.click(screen.getByRole("button", { name: "קריאה לעזרה — חדר 2" }));
    await waitFor(() => expect(openDialog()).toHaveTextContent("למי לקרוא"));

    // The room is released underneath: the tile, and its trigger, unmount.
    getFloor.mockResolvedValue(floor([room({ assignment: null })]));
    await act(async () => {
      await vi.advanceTimersByTimeAsync(5_000);
    });

    fireEvent.click(screen.getByRole("button", { name: "ביטול" }));
    await waitFor(() => expect(dialogs().some((node) => node.open)).toBe(false));

    expect(document.activeElement).toBe(screen.getByRole("heading", { level: 2 }));
    expect(document.activeElement).not.toBe(document.body);
  });

  it("does NOT yank focus back to the trigger when something else already took it", async () => {
    // ⚠ THIS BLOCK EXISTS BECAUSE THE MUTATION CAME BACK GREEN WITHOUT IT.
    // Deleting MOVE G's `document.activeElement === document.body` guard — the
    // shipped MOVE-4 shape it copies — left the whole suite passing, because a
    // real <dialog> traps focus and every other path leaves it on <body>.
    //
    // The reachable case is a SECOND focus move landing in the same commit as
    // the close: this feature has four of them (MOVE A, B, C and H), and one
    // firing while the dialog closes must win, because it is the one responding
    // to what just changed on screen.
    mount();
    await screen.findByText("אין עכשיו קריאות פתוחות.");
    await openFromCentre();
    // ⚠ BY NAME: the Modal renders its own h2 in the top layer, so «level 2»
    // alone matches two headings while the dialog is open.
    const elsewhere = screen.getByRole("heading", { name: "צוות בקומה" });
    elsewhere.focus();

    fireEvent.click(screen.getByRole("button", { name: "ביטול" }));
    await waitFor(() => expect(dialogs().some((node) => node.open)).toBe(false));

    expect(document.activeElement).toBe(elsewhere);
  });
});

// --- AC14's sibling case -------------------------------------------------------

describe("AC14's sibling case", () => {
  it("does NOT move focus when an SOS overlay rises while this dialog is open", async () => {
    // ⚠ ASSERTED, because «the guard happens to cover it» is exactly the kind of
    // accidental correctness a later refactor deletes. MOVE A's document.body
    // guard resolves it with no extra code — focus is inside the dialog.
    mount();
    await screen.findByText("אין עכשיו קריאות פתוחות.");
    const dialog = await openFromCentre();
    const note = within(dialog).getByLabelText("מה צריך");
    note.focus();
    fireEvent.change(note, { target: { value: "צריך" } });

    getSos.mockResolvedValue({
      alerts: [
        raised({
          id: "eeeeeeee-0000-0000-0000-000000000005",
          raised_by: DANA,
          raised_by_name: "דנה כהן",
          for_me: true,
        }),
      ],
      server_now: NOW,
      unread_notifications: 0,
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(5_000);
    });
    await waitFor(() => expect(document.querySelector("[data-alert-id]")).not.toBeNull());

    expect(document.activeElement).toBe(note);
    expect((note as HTMLInputElement).value).toBe("צריך");
  });
});

// --- axe ------------------------------------------------------------------------

describe("axe", () => {
  it("passes with zero violations over the open dialog", async () => {
    getFloor.mockResolvedValue(
      floor([], [ME, DANA_CARD, card({ status: "break", break_started_at: NOW })]),
    );
    const { container } = mount();
    await screen.findByText("אין עכשיו קריאות פתוחות.");
    await openFromCentre();

    const results = await run(container);
    expect(results.violations).toEqual([]);
  });
});
