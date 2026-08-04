import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { run } from "axe-core";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import "../i18n";
import type { FloorResponse, SosAlert, StaffCard } from "../api";
import { FloorPanel } from "../components/FloorPanel";
import { SosProvider } from "../lib/sos";

/**
 * ⚠ `SosCentre` is mounted THROUGH `FloorPanel` and never on its own. It is a
 * child (spec D16): it owns no timer, no pause control, no freshness row and no
 * announced region — it receives `paused`, writes its cues into `FloorPanel`'s
 * single role="status", and takes its alerts from `useSos()` because they belong
 * to the app-level poll and there is exactly one of them. A direct render would
 * stub exactly the mechanisms its correctness depends on.
 *
 * ⚠ AND IT OWNS ITS OWN ERROR STATE, REF AND FOCUS RULE (MOVE H). `FloorPanel`
 * has exactly one of everything it would otherwise share — `cardError`,
 * `cardAlertRef`, and an UNCONDITIONAL focus move on every non-null transition —
 * so sharing them would steal focus into a STAFF CARD's alert node through the
 * exact guard-less effect MOVE D warns against copying, and `cardError.id` is a
 * staff-card id, so the render predicate would collide semantically too.
 */

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
      getSos: vi.fn(),
      raiseSos: vi.fn(),
      acceptSos: vi.fn(),
      resolveSos: vi.fn(),
      cancelSos: vi.fn(),
    },
  };
});

const { api, ApiError } = await import("../api");
const getFloor = vi.mocked(api.getFloor);
const getSos = vi.mocked(api.getSos);
const acceptSos = vi.mocked(api.acceptSos);
const resolveSos = vi.mocked(api.resolveSos);
const cancelSos = vi.mocked(api.cancelSos);
const listFloorClients = vi.mocked(api.listFloorClients);

const NOW = "2026-08-04T11:07:00Z";
// 11:04Z is three minutes before NOW — «כבר 3 דק'», the deck's own worked row.
const RAISED_AT = "2026-08-04T11:04:00Z";
const LATER_AT = "2026-08-04T11:06:00Z";

const SELF_ID = "11111111-1111-1111-1111-111111111111";
const DANA = "22222222-2222-2222-2222-222222222222";
const NOA = "33333333-3333-3333-3333-333333333333";
const ALERT_A = "aaaaaaaa-0000-0000-0000-00000000000a";
const ALERT_B = "bbbbbbbb-0000-0000-0000-00000000000b";

function card(overrides: Partial<StaffCard> = {}): StaffCard {
  return {
    id: NOA,
    display_name: "נועה לוי",
    role: "seamstress",
    status: "available",
    break_started_at: null,
    occupancy: null,
    ...overrides,
  };
}

const ME = card({ id: SELF_ID, display_name: "רותם", role: "owner" });

function floor(staff: StaffCard[] = [ME, card()]): FloorResponse {
  return { staff, rooms: [], server_now: NOW };
}

function alertRow(overrides: Partial<SosAlert> = {}): SosAlert {
  return {
    id: ALERT_A,
    status: "open",
    raised_by: DANA,
    raised_by_name: "דנה כהן",
    target_staff_user_id: null,
    target_name: null,
    room_label: "חדר 2",
    note: "צריך סיכות",
    accepted_by: null,
    accepted_by_name: null,
    acknowledged_at: null,
    created_at: RAISED_AT,
    escalated: false,
    stalled: false,
    // The overlay's business, not the centre's: the panel lists every alert the
    // caller may SEE, and `for_me` only decides whether it RISES.
    for_me: false,
    ...overrides,
  };
}

function sosPage(alerts: SosAlert[]) {
  return { alerts, server_now: NOW };
}

function mount(props: { selfId?: string; role?: string } = {}) {
  return render(
    <SosProvider>
      <FloorPanel
        selfId={props.selfId ?? SELF_ID}
        role={props.role ?? "owner"}
      />
    </SosProvider>,
  );
}

function rows(): HTMLElement[] {
  return Array.from(document.querySelectorAll("[data-alert-id]"));
}

function row(id: string): HTMLElement {
  const node = document.querySelector(`[data-alert-id="${id}"]`);
  if (!(node instanceof HTMLElement)) {
    throw new Error(`no row for ${id}`);
  }
  return node;
}

async function advance(ms: number) {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });
}

/**
 * ⚠ THE ONLY WAY TO REACH `<body>` IN jsdom ONCE A CONTROL IS `disabled`.
 *
 * `Button` is `disabled={disabled || loading}`, so Chromium blurs the tapped
 * control the instant the request starts. jsdom does not — and
 * `HTMLElement.blur()` BAILS OUT on an element that is not a focusable area, so
 * the `control.blur()` MOVE H's tests use is a NO-OP on a disabled control. A
 * scratch node outside React's tree is focusable, so blurring THAT really does
 * land on `<body>` and reproduces the browser's precondition.
 */
function dropFocusToBody() {
  const scratch = document.createElement("button");
  document.body.appendChild(scratch);
  scratch.focus();
  scratch.blur();
  scratch.remove();
}

beforeEach(() => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  vi.setSystemTime(new Date(NOW));
  getFloor.mockReset();
  getSos.mockReset();
  acceptSos.mockReset();
  resolveSos.mockReset();
  cancelSos.mockReset();
  listFloorClients.mockReset();
  listFloorClients.mockResolvedValue({ clients: [], truncated: false });
  getFloor.mockResolvedValue(floor());
  getSos.mockResolvedValue(sosPage([]));
});

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

// --- the state this panel is in almost always ---------------------------------

describe("empty — which is what it looks like almost always", () => {
  it("renders a heading row, the trigger and ONE muted line, and no EmptyState at all", async () => {
    mount();
    await screen.findByText("אין עכשיו קריאות פתוחות.");

    expect(
      screen.getByRole("heading", { level: 3, name: "קריאות עזרה" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "קריאה לעזרה" }),
    ).toBeInTheDocument();
    // ⚠ NOT an EmptyState: py-12 + font-display text-xl is ≈140px announcing
    // that there is no emergency, on a screen a staffer reads fifty times a
    // shift. The condition EmptyState exists for is content that SHOULD be here
    // and is not; no alerts is the desired state.
    const line = screen.getByText("אין עכשיו קריאות פתוחות.");
    expect(line.className).toContain("text-sm");
    expect(line.className).not.toContain("font-display");
    expect(rows()).toHaveLength(0);
  });

  it("offers the trigger to a seamstress too — it is the ONE control that encodes no permission", async () => {
    mount({ selfId: NOA, role: "seamstress" });
    await screen.findByText("אין עכשיו קריאות פתוחות.");

    expect(
      screen.getByRole("button", { name: "קריאה לעזרה" }),
    ).toBeInTheDocument();
  });
});

// --- populated ----------------------------------------------------------------

describe("populated — one row per alert, oldest first", () => {
  it("carries raiser, room, note, elapsed and the STATUS WORD in exactly one Badge", async () => {
    getSos.mockResolvedValue(sosPage([alertRow()]));
    mount();
    await screen.findByText("דנה כהן");

    const item = row(ALERT_A);
    expect(item).toHaveTextContent("דנה כהן");
    expect(item).toHaveTextContent("חדר 2");
    expect(item).toHaveTextContent("צריך סיכות");
    expect(item).toHaveTextContent("כבר 3 דק'");
    expect(item).toHaveTextContent("פתוחה");
    // ONE pill per row and it is the status. The raiser is muted words in a bare
    // <bdi> and never a second Badge.
    expect(item.querySelectorAll("span.rounded-full")).toHaveLength(1);
  });

  it("puts escalation and the stall beside the Badge as WORDS, never as a second pill", async () => {
    getSos.mockResolvedValue(
      sosPage([
        alertRow({ escalated: true }),
        alertRow({
          id: ALERT_B,
          created_at: LATER_AT,
          status: "accepted",
          accepted_by: NOA,
          accepted_by_name: "נועה לוי",
          stalled: true,
        }),
      ]),
    );
    mount();
    await screen.findByText("ללא מענה");

    expect(row(ALERT_A)).toHaveTextContent("ללא מענה");
    expect(row(ALERT_A).querySelectorAll("span.rounded-full")).toHaveLength(1);
    expect(row(ALERT_B)).toHaveTextContent("אין תזוזה מאז שאושרה");
    expect(row(ALERT_B)).toHaveTextContent("מטופלת");
    expect(row(ALERT_B).querySelectorAll("span.rounded-full")).toHaveLength(1);
    // Oldest first — the same order as the overlay, so the two screens never
    // disagree about which emergency is next.
    expect(rows().map((node) => node.getAttribute("data-alert-id"))).toEqual([
      ALERT_A,
      ALERT_B,
    ]);
  });

  it("answers «who is coming» on an accepted row, and admits it when her staff row is gone", async () => {
    // ⚠ The acceptor is «מיכל ברק» and not «נועה לוי» ON PURPOSE: «נועה לוי» is
    // also a STAFF CARD on this screen, and a name that appears twice makes a
    // getByText assertion pass for the wrong reason.
    getSos.mockResolvedValue(
      sosPage([
        alertRow({
          status: "accepted",
          accepted_by: NOA,
          accepted_by_name: "מיכל ברק",
        }),
        alertRow({
          id: ALERT_B,
          created_at: LATER_AT,
          status: "accepted",
          accepted_by: NOA,
          accepted_by_name: null,
        }),
      ]),
    );
    mount();
    // `isolateBidi` splits the sentence across nodes, so wait on the rows.
    await waitFor(() => expect(rows()).toHaveLength(2));

    expect(row(ALERT_A)).toHaveTextContent("מיכל ברק מגיעה.");
    expect(row(ALERT_B)).toHaveTextContent("מישהי כבר מגיעה.");
  });

  it("names a removed raiser and a missing room without a second key", async () => {
    getSos.mockResolvedValue(
      sosPage([
        alertRow({ raised_by_name: null, room_label: null, note: null }),
      ]),
    );
    mount();
    await screen.findByText("אשת צוות שאינה ברשימה");

    expect(row(ALERT_A)).toHaveTextContent("לא בחדר מדידה");
  });
});

// --- AC21: which control EXISTS is the rendered form of the permission rules ---

describe("AC21 — absence, never a disabled control", () => {
  it("gives a seamstress on somebody else's alert NO accept, NO resolve and NO cancel", async () => {
    // ⚠ This is what keeps the 403-is-terminal rule unreachable BY DESIGN rather
    // than by luck: usePoll.terminalOf returns "access" for any 403 and the
    // floor panel clears every card — so a rendered control reaching a route its
    // caller may not use blanks a seamstress's only screen.
    getSos.mockResolvedValue(
      sosPage([alertRow({ target_staff_user_id: DANA })]),
    );
    mount({ selfId: NOA, role: "seamstress" });
    await screen.findByText("דנה כהן");

    const item = row(ALERT_A);
    expect(
      within(item).queryByRole("button", { name: /אני מגיעה/ }),
    ).toBeNull();
    expect(within(item).queryByRole("button", { name: /נפתר/ })).toBeNull();
    expect(
      within(item).queryByRole("button", { name: /ביטול הקריאה/ }),
    ).toBeNull();
    const disabled = Array.from(item.querySelectorAll("button")).filter(
      (node) => node.disabled,
    );
    expect(disabled).toHaveLength(0);
  });

  it("gives an owner all three", async () => {
    getSos.mockResolvedValue(
      sosPage([alertRow({ target_staff_user_id: DANA })]),
    );
    mount();
    await screen.findByText("דנה כהן");

    const item = row(ALERT_A);
    expect(
      within(item).getByRole("button", { name: /אני מגיעה/ }),
    ).toBeInTheDocument();
    expect(
      within(item).getByRole("button", { name: /נפתר/ }),
    ).toBeInTheDocument();
    expect(
      within(item).getByRole("button", { name: /ביטול הקריאה/ }),
    ).toBeInTheDocument();
  });

  it("gives an OWNER NO accept on the page SHE raised — resolve and cancel only", async () => {
    // ⚠ THE ELEVATED BRANCH HAD NO `raised_by` TERM, server or client. An owner
    // alone in fitting room 2 raises to the shift-manager ROLE — the dialog's
    // first and DEFAULT option — and her own row renders «אני מגיעה» first. One
    // tap: `_escalated` short-circuits on `status != OPEN` so the alert stops
    // escalating forever, and `_for_me`'s accepted branch returns
    // `stalled and elevated`, which is False for the raiser at every t. The
    // overlay drops on every device for the two minutes `_stalled` takes, and if
    // she is the only elevated staffer signed in it never rises again at all.
    getSos.mockResolvedValue(
      sosPage([alertRow({ raised_by: SELF_ID, raised_by_name: "רותם המנהלת" })]),
    );
    mount();
    await screen.findByText("רותם המנהלת");

    const item = row(ALERT_A);
    expect(
      within(item).queryByRole("button", { name: /אני מגיעה/ }),
    ).toBeNull();
    expect(
      within(item).getByRole("button", { name: /נפתר/ }),
    ).toBeInTheDocument();
    expect(
      within(item).getByRole("button", { name: /ביטול הקריאה/ }),
    ).toBeInTheDocument();
  });

  it("gives the NAMED TARGET an accept even though she is a seamstress", async () => {
    getSos.mockResolvedValue(
      sosPage([alertRow({ target_staff_user_id: NOA })]),
    );
    mount({ selfId: NOA, role: "seamstress" });
    await screen.findByText("דנה כהן");

    expect(
      within(row(ALERT_A)).getByRole("button", { name: /אני מגיעה/ }),
    ).toBeInTheDocument();
    expect(
      within(row(ALERT_A)).queryByRole("button", { name: /ביטול הקריאה/ }),
    ).toBeNull();
  });

  it("gives the RAISER cancel and resolve and NO accept — she may not accept her own page", async () => {
    getSos.mockResolvedValue(
      sosPage([alertRow({ raised_by: NOA, raised_by_name: "נועה לוי" })]),
    );
    mount({ selfId: NOA, role: "seamstress" });
    // «נועה לוי» is a staff card here too, so wait on something only the row has.
    await screen.findByText("צריך סיכות");

    const item = row(ALERT_A);
    expect(
      within(item).queryByRole("button", { name: /אני מגיעה/ }),
    ).toBeNull();
    expect(
      within(item).getByRole("button", { name: /ביטול הקריאה/ }),
    ).toBeInTheDocument();
    expect(
      within(item).getByRole("button", { name: /נפתר/ }),
    ).toBeInTheDocument();
  });

  it("drops the accept once the alert is accepted, and keeps resolve for the acceptor", async () => {
    getSos.mockResolvedValue(
      sosPage([
        alertRow({
          status: "accepted",
          accepted_by: NOA,
          accepted_by_name: "נועה לוי",
        }),
      ]),
    );
    mount({ selfId: NOA, role: "seamstress" });
    await screen.findByText("דנה כהן");

    const item = row(ALERT_A);
    expect(
      within(item).queryByRole("button", { name: /אני מגיעה/ }),
    ).toBeNull();
    expect(
      within(item).queryByRole("button", { name: /ביטול הקריאה/ }),
    ).toBeNull();
    expect(
      within(item).getByRole("button", { name: /נפתר/ }),
    ).toBeInTheDocument();
  });
});

// --- the actions and every sentence their refusals carry ----------------------

describe("the three actions", () => {
  it("patches the row FROM THE RESPONSE, disables in flight, and fires ONE request on a double tap", async () => {
    getSos.mockResolvedValue(sosPage([alertRow()]));
    mount();
    await screen.findByText("דנה כהן");

    let settle: (value: SosAlert) => void = () => {};
    acceptSos.mockReturnValue(
      new Promise<SosAlert>((resolve) => (settle = resolve)),
    );
    const accept = within(row(ALERT_A)).getByRole("button", {
      name: /אני מגיעה/,
    });
    fireEvent.click(accept);
    fireEvent.click(accept);
    await act(async () => {
      await Promise.resolve();
    });

    expect(acceptSos).toHaveBeenCalledTimes(1);
    expect(
      within(row(ALERT_A)).getByRole("button", { name: /אני מגיעה/ }),
    ).toBeDisabled();

    await act(async () => {
      settle(
        alertRow({
          status: "accepted",
          accepted_by: SELF_ID,
          accepted_by_name: "רותם",
        }),
      );
      await Promise.resolve();
    });
    await waitFor(() => expect(row(ALERT_A)).toHaveTextContent("מטופלת"));
    expect(row(ALERT_A)).toHaveTextContent("רותם מגיעה.");
  });

  it("names the owner on a 409 and admits it does not know when `details` is absent", async () => {
    getSos.mockResolvedValue(sosPage([alertRow()]));
    mount();
    await screen.findByText("דנה כהן");

    acceptSos.mockRejectedValueOnce(
      new ApiError(409, "SOS_ALREADY_ACCEPTED", "taken", {
        staff_display_name: "נועה לוי",
      }),
    );
    fireEvent.click(
      within(row(ALERT_A)).getByRole("button", { name: /אני מגיעה/ }),
    );
    await waitFor(() =>
      expect(row(ALERT_A)).toHaveTextContent("נועה לוי כבר מגיעה."),
    );

    acceptSos.mockRejectedValueOnce(
      new ApiError(409, "SOS_ALREADY_ACCEPTED", "taken"),
    );
    fireEvent.click(
      within(row(ALERT_A)).getByRole("button", { name: /אני מגיעה/ }),
    );
    await waitFor(() =>
      expect(row(ALERT_A)).toHaveTextContent("מישהי אחרת כבר מגיעה."),
    );
  });

  it("carries the REMEDY on a cancel-after-accept, in both its variants", async () => {
    // ⚠ The asymmetry with resolve is the point: a colleague is already walking
    // to that curtain, and silently cancelling would send her to an empty room
    // and teach her that accepting means nothing. So the sentence carries the
    // remedy, and the remedy is one word over.
    getSos.mockResolvedValue(sosPage([alertRow()]));
    mount();
    await screen.findByText("דנה כהן");

    cancelSos.mockRejectedValueOnce(
      new ApiError(409, "SOS_ALREADY_ACCEPTED", "taken", {
        staff_display_name: "נועה לוי",
      }),
    );
    fireEvent.click(
      within(row(ALERT_A)).getByRole("button", { name: /ביטול הקריאה/ }),
    );
    await waitFor(() =>
      expect(row(ALERT_A)).toHaveTextContent(
        "נועה לוי כבר מגיעה. אפשר לסמן «נפתר» במקום.",
      ),
    );

    cancelSos.mockRejectedValueOnce(
      new ApiError(409, "SOS_ALREADY_ACCEPTED", "taken"),
    );
    fireEvent.click(
      within(row(ALERT_A)).getByRole("button", { name: /ביטול הקריאה/ }),
    );
    await waitFor(() =>
      expect(row(ALERT_A)).toHaveTextContent(
        "מישהי אחרת כבר מגיעה. אפשר לסמן «נפתר» במקום.",
      ),
    );
  });

  it("treats a 404 as NOT terminal — the alert vanished, her access did not", async () => {
    getSos.mockResolvedValue(sosPage([alertRow()]));
    mount();
    await screen.findByText("דנה כהן");

    resolveSos.mockRejectedValueOnce(new ApiError(404, "NOT_FOUND", "gone"));
    fireEvent.click(within(row(ALERT_A)).getByRole("button", { name: /נפתר/ }));

    await waitFor(() =>
      expect(row(ALERT_A)).toHaveTextContent("הקריאה כבר לא פתוחה."),
    );
    expect(
      screen.getByRole("heading", { level: 3, name: "קריאות עזרה" }),
    ).toBeInTheDocument();
  });

  it("lets a 403 END THE CHANNEL and announces NOTHING — never a success cue over a dead one", async () => {
    // ⚠ THE PLAN SAYS «a 403 IS terminal [for the whole floor panel]» AND THAT
    // IS FALSE IN THIS ARCHITECTURE. `SosCentre`'s actions run through the
    // APP-LEVEL provider's `mutate`, which classifies terminals against the SOS
    // poll — a different loop from `FloorPanel`'s. So an SOS 403 ends the
    // CHANNEL (the overlay's persistent strip says so on all thirteen sections)
    // and `FloorPanel`'s own terminal panel waits for its own poll's 403, which
    // lands within one tick.
    //
    // What matters here is what the provider's contract makes easy to get
    // wrong: `mutate` returns `null` on a terminal exactly as it does on a
    // success, so a cue fired on `failure === null` would announce «הקריאה
    // נסגרה.» into a live region over a channel that had just died. It must not.
    getSos.mockResolvedValue(sosPage([alertRow()]));
    mount();
    await screen.findByText("דנה כהן");
    const cue = screen.getByTestId("floor-cue");

    resolveSos.mockRejectedValueOnce(new ApiError(403, "FORBIDDEN", "nope"));
    fireEvent.click(within(row(ALERT_A)).getByRole("button", { name: /נפתר/ }));
    await act(async () => {
      await Promise.resolve();
    });

    expect(cue).not.toHaveTextContent("הקריאה נסגרה.");
    expect(row(ALERT_A)).not.toHaveTextContent("הפעולה לא הושלמה");
  });

  it("renders sos.error.actionFailed on an unmapped failure and NEVER the console's fallback", async () => {
    // A failed ACCEPT means only that SHE did not claim it — the alert is still
    // open, still rising elsewhere and still escalating — so «נסי שוב» is right
    // and naming the manual fallback would be wrong. That is why the raise has a
    // different string.
    getSos.mockResolvedValue(sosPage([alertRow()]));
    mount();
    await screen.findByText("דנה כהן");

    acceptSos.mockRejectedValueOnce(new Error("wifi"));
    fireEvent.click(
      within(row(ALERT_A)).getByRole("button", { name: /אני מגיעה/ }),
    );

    await waitFor(() =>
      expect(row(ALERT_A)).toHaveTextContent("הפעולה לא הושלמה. נסי שוב."),
    );
    expect(row(ALERT_A)).not.toHaveTextContent("אירעה שגיאה בלתי צפויה");
  });
});

// --- MOVE H --------------------------------------------------------------------

describe("MOVE H — SosCentre owns its own error state, ref and focus rule", () => {
  it("moves focus into the ROW's own alert, inside the SOS list and not a staff card", async () => {
    getSos.mockResolvedValue(sosPage([alertRow()]));
    mount();
    await screen.findByText("דנה כהן");

    const control = within(row(ALERT_A)).getByRole("button", {
      name: /אני מגיעה/,
    });
    control.focus();
    acceptSos.mockRejectedValueOnce(new ApiError(404, "NOT_FOUND", "gone"));
    fireEvent.click(control);
    // ⚠ EXPLICIT BLUR: Button is disabled={disabled||loading} so a real browser
    // blurs it here and jsdom does not.
    control.blur();

    await waitFor(() =>
      expect(row(ALERT_A)).toHaveTextContent("הקריאה כבר לא פתוחה."),
    );
    const active = document.activeElement as HTMLElement;
    expect(active.closest("[data-alert-id]")).toBe(row(ALERT_A));
    // The collision DC-7 exists to prevent: FloorPanel's cardError.id is a STAFF
    // CARD id, so a shared pair would render this alert nowhere and focus a
    // staff card's node.
    expect(active.closest("[data-staff-id]")).toBeNull();
  });

  it("does NOT pull her out of a text input when the refusal lands", async () => {
    getSos.mockResolvedValue(sosPage([alertRow()]));
    mount();
    await screen.findByText("דנה כהן");

    const control = within(row(ALERT_A)).getByRole("button", {
      name: /אני מגיעה/,
    });
    let reject: (error: unknown) => void = () => {};
    acceptSos.mockReturnValue(new Promise((_resolve, r) => (reject = r)));
    fireEvent.click(control);
    control.blur();

    // She moved on while the request was in the air — the break control on a
    // staff card is the nearest real thing to move to on this screen.
    const elsewhere = screen.getAllByRole("button", {
      name: /להפסקה/,
    })[0] as HTMLElement;
    elsewhere.focus();

    await act(async () => {
      reject(new ApiError(404, "NOT_FOUND", "gone"));
      await Promise.resolve();
    });
    await waitFor(() =>
      expect(row(ALERT_A)).toHaveTextContent("הקריאה כבר לא פתוחה."),
    );

    expect(document.activeElement).toBe(elsewhere);
  });
});

// --- MOVE I: the SUCCESS path had no focus owner at all ------------------------

describe("MOVE I — a SUCCESSFUL action restores focus instead of dropping it on <body>", () => {
  it("a resolve that removes the row lands on the SOS-centre heading, never <body>", async () => {
    // ⚠ DC-7 gave `SosCentre` its own FAILURE-path pair (MOVE H) and left the
    // SUCCESS path with no owner: `grep '\.focus()'` returned exactly one hit,
    // inside `rowError !== null`. `FloorPanel`'s three restores cannot cover an
    // SOS row — `restoreFocusRef` is only ever set inside `toggle`, the
    // `cardError` reclaim keys on a state that never transitions here, and
    // `focusHeadingRef` reads `[data-staff-id]`. So a keyboard user tapping
    // «נפתר» got: control goes `disabled` → browser blurs to <body> → the row
    // unmounts → nothing restores → her next Tab restarts at the top of the
    // document, with the only feedback written into a region she is not in.
    getSos.mockResolvedValue(sosPage([alertRow()]));
    mount();
    await screen.findByText("דנה כהן");
    const control = within(row(ALERT_A)).getByRole("button", { name: /נפתר/ });
    control.focus();
    let land: (alert: SosAlert) => void = () => {};
    resolveSos.mockReturnValue(
      new Promise<SosAlert>((resolve) => {
        land = resolve;
      }),
    );

    fireEvent.click(control);
    dropFocusToBody();
    expect(document.activeElement).toBe(document.body);

    await act(async () => {
      land(alertRow({ status: "resolved" }));
      await Promise.resolve();
    });
    await waitFor(() => expect(rows()).toHaveLength(0));

    // ⚠ `waitFor`: the row leaving and MOVE I running are two different moments,
    // and a bare assertion here is the shape that flaked three focus tests in
    // this suite. NOT vacuous — delete the intent and focus stays on `<body>`.
    await waitFor(() =>
      expect(document.activeElement).toBe(
        screen.getByRole("heading", { level: 3, name: "קריאות עזרה" }),
      ),
    );
    expect(document.activeElement).not.toBe(document.body);
  });

  it("an accept that removes only the tapped control lands on the row's remaining control", async () => {
    getSos.mockResolvedValue(sosPage([alertRow()]));
    mount();
    await screen.findByText("דנה כהן");
    const control = within(row(ALERT_A)).getByRole("button", {
      name: /אני מגיעה/,
    });
    control.focus();
    let land: (alert: SosAlert) => void = () => {};
    acceptSos.mockReturnValue(
      new Promise<SosAlert>((resolve) => {
        land = resolve;
      }),
    );

    fireEvent.click(control);
    dropFocusToBody();

    await act(async () => {
      land(alertRow({ status: "accepted", accepted_by_name: "רותם" }));
      await Promise.resolve();
    });
    await waitFor(() =>
      expect(
        within(row(ALERT_A)).queryByRole("button", { name: /אני מגיעה/ }),
      ).toBeNull(),
    );

    await waitFor(() =>
      expect(
        (document.activeElement as HTMLElement).closest("[data-alert-id]"),
      ).toBe(row(ALERT_A)),
    );
    expect(document.activeElement).not.toBe(document.body);
  });

  it("the STEAL direction — it does NOT pull her out of a control she moved to", async () => {
    // The other half of F41's lesson: the first fix for a dropped focus shipped
    // a focus STEAL. Delete the `active === document.body || inside` guard and
    // this reds.
    getSos.mockResolvedValue(sosPage([alertRow()]));
    mount();
    await screen.findByText("דנה כהן");
    const control = within(row(ALERT_A)).getByRole("button", { name: /נפתר/ });
    control.focus();
    let land: (alert: SosAlert) => void = () => {};
    resolveSos.mockReturnValue(
      new Promise<SosAlert>((resolve) => {
        land = resolve;
      }),
    );

    fireEvent.click(control);
    const elsewhere = screen.getAllByRole("button", {
      name: /להפסקה/,
    })[0] as HTMLElement;
    elsewhere.focus();

    await act(async () => {
      land(alertRow({ status: "resolved" }));
      await Promise.resolve();
    });
    await waitFor(() => expect(rows()).toHaveLength(0));
    // …and settle, so a steal firing one flush LATE is caught rather than raced.
    await act(async () => {
      await Promise.resolve();
    });

    expect(document.activeElement).toBe(elsewhere);
  });
});

// --- AC18: the paused freeze and its one exemption ----------------------------

describe("AC18 — the paused freeze, and the one row it lets through", () => {
  it("freezes the rendered list against a tick that lands while paused", async () => {
    // The pause control is «השהיה — עדכון הצוות» and governs the region it sits
    // in, which after this feature contains a list fed by a loop the pause does
    // NOT stop. A pause control whose region keeps moving is an SC 2.2.2 failure
    // that passes axe.
    getSos.mockResolvedValue(sosPage([alertRow()]));
    mount();
    await screen.findByText("דנה כהן");

    fireEvent.click(
      screen.getByRole("button", { name: "השהיה — עדכון הצוות" }),
    );
    getSos.mockResolvedValue(
      sosPage([
        alertRow(),
        alertRow({
          id: ALERT_B,
          created_at: LATER_AT,
          raised_by_name: "מיכל ברק",
        }),
      ]),
    );
    await advance(4_000);

    expect(rows().map((node) => node.getAttribute("data-alert-id"))).toEqual([
      ALERT_A,
    ]);
    expect(document.body.textContent).not.toContain("מיכל ברק");
  });

  it("lets THIS staffer's own new alert through anyway — the freeze's one exemption", async () => {
    // ⚠ Both raise triggers are on the floor section, the overlay never rises
    // for her own page, and a frozen list will not add it — so a staffer who
    // paused the board and then raised would see her own new alert NOWHERE. The
    // freeze exists so the pause control does not lie about THE POLL; a row she
    // created one tap ago is not the poll moving underneath her.
    getSos.mockResolvedValue(sosPage([]));
    mount();
    await screen.findByText("אין עכשיו קריאות פתוחות.");

    fireEvent.click(
      screen.getByRole("button", { name: "השהיה — עדכון הצוות" }),
    );
    getSos.mockResolvedValue(
      sosPage([
        alertRow({ id: ALERT_B, raised_by: DANA, raised_by_name: "מיכל ברק" }),
        alertRow({ raised_by: SELF_ID, raised_by_name: "רותם" }),
      ]),
    );
    // ⚠ SIX seconds: the SOS loop beats at 5 000 with nothing on screen and only
    // drops to 2 000 once an alert is live, so a 4 000 advance lands NO tick and
    // the block would pass without the exemption existing at all.
    await advance(6_000);

    expect(rows().map((node) => node.getAttribute("data-alert-id"))).toEqual([
      ALERT_A,
    ]);
    // «רותם» is her own staff card as well, so assert INSIDE the row.
    expect(row(ALERT_A)).toHaveTextContent("רותם");
  });
});

// --- the cue region -------------------------------------------------------------

describe("the cue region is FloorPanel's, and the poll never writes into it", () => {
  it("announces an action's outcome there", async () => {
    getSos.mockResolvedValue(sosPage([alertRow()]));
    mount();
    await screen.findByText("דנה כהן");

    resolveSos.mockResolvedValue(alertRow({ status: "resolved" }));
    fireEvent.click(within(row(ALERT_A)).getByRole("button", { name: /נפתר/ }));

    await waitFor(() =>
      expect(screen.getByTestId("floor-cue")).toHaveTextContent(
        "הקריאה נסגרה.",
      ),
    );
  });

  it("leaves the cue byte-identical across several consecutive SOS ticks", async () => {
    // ⚠ Driven over SEVERAL ticks WITH THE CUE ALREADY POPULATED, because
    // assigning a byte-identical string to a text node still produces a real
    // childList mutation inside role="status" — and a single-tick assertion
    // passes against the broken version whenever the cue starts empty.
    getSos.mockResolvedValue(sosPage([alertRow()]));
    mount();
    await screen.findByText("דנה כהן");
    resolveSos.mockResolvedValue(alertRow({ status: "resolved" }));
    fireEvent.click(within(row(ALERT_A)).getByRole("button", { name: /נפתר/ }));
    await waitFor(() =>
      expect(screen.getByTestId("floor-cue")).toHaveTextContent(
        "הקריאה נסגרה.",
      ),
    );

    const cue = screen.getByTestId("floor-cue");
    const settled = cue.textContent;
    for (let tick = 0; tick < 3; tick += 1) {
      await advance(5_000);
      expect(cue.textContent).toBe(settled);
    }
  });
});

// --- axe -----------------------------------------------------------------------

describe("axe", () => {
  it("passes with zero violations over the empty panel and the populated list", async () => {
    // Explicitly NOT sufficient: axe has no rule for SC 2.2.2, so the freeze
    // block above is the only automated coverage of a Level A criterion that
    // IS 5568 makes legally binding here.
    getSos.mockResolvedValue(
      sosPage([
        alertRow({ escalated: true }),
        alertRow({
          id: ALERT_B,
          created_at: LATER_AT,
          status: "accepted",
          accepted_by: NOA,
          accepted_by_name: "נועה לוי",
          stalled: true,
        }),
      ]),
    );
    const { container } = mount();
    await screen.findByText("ללא מענה");

    const results = await run(container);
    expect(results.violations).toEqual([]);
  });
});
