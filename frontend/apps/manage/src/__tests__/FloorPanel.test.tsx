import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { run } from "axe-core";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import "../i18n";
import type { FloorResponse, Occupancy, Room, StaffCard } from "../api";
import { FloorPanel } from "../components/FloorPanel";
import { IDLE_STOP_MS, POLL_INTERVAL_MS } from "../lib/usePoll";

vi.mock("../api", async () => {
  const actual = await vi.importActual<typeof import("../api")>("../api");
  return {
    ApiError: actual.ApiError,
    errorMessage: actual.errorMessage,
    api: {
      getFloor: vi.fn(),
      startStaffBreak: vi.fn(),
      endStaffBreak: vi.fn(),
      // F36: the panel now renders RoomsPanel, whose one-shot client picker
      // fires on mount. Infrastructure, not an expectation — every assertion
      // below is untouched (spec D15).
      listFloorClients: vi.fn(),
    },
  };
});

const { api, ApiError } = await import("../api");
const getFloor = vi.mocked(api.getFloor);
const startStaffBreak = vi.mocked(api.startStaffBreak);
const endStaffBreak = vi.mocked(api.endStaffBreak);
const listFloorClients = vi.mocked(api.listFloorClients);

// 11:07Z is 14:07 in Jerusalem (IDT, UTC+3) and 07:07 in New York — and the test
// script pins TZ=America/New_York, so an unzoned read prints 07:07 and every
// time assertion below fails loudly rather than quietly.
const NOW = "2026-08-04T11:07:00Z";
const BREAK_BEGAN = "2026-08-04T08:20:00Z"; // 11:20 Jerusalem

const SELF_ID = "11111111-1111-1111-1111-111111111111";
const OTHER_ID = "22222222-2222-2222-2222-222222222222";

function card(overrides: Partial<StaffCard> = {}): StaffCard {
  return {
    id: OTHER_ID,
    display_name: "נועה לוי",
    role: "seamstress",
    status: "available",
    break_started_at: null,
    occupancy: null,
    ...overrides,
  };
}

// F36 widened the envelope with `rooms` and `server_now`. Both are DEFAULTED
// here so every shipped call site stays exactly as it was — D15's acceptance
// rule is about expectations, and a fixture that would not compile is not one.
function floor(staff: StaffCard[], rooms: Room[] = []): FloorResponse {
  return { staff, rooms, server_now: NOW, waitlist: { entries: [], truncated: false } };
}

// 10:25Z is 42 minutes before NOW, and 42 is the deck's own worked example.
const ASSIGNED_AT = "2026-08-04T10:25:00Z";
const ROOM_ID = "33333333-3333-3333-3333-333333333333";
const ASSIGNMENT_ID = "44444444-4444-4444-4444-444444444444";

function occupancy(overrides: Partial<Occupancy> = {}): Occupancy {
  return {
    assignment_id: ASSIGNMENT_ID,
    fitting_room_id: ROOM_ID,
    room_label: "חדר 2",
    client_label: "מיכל",
    assigned_at: ASSIGNED_AT,
    ...overrides,
  };
}

const ME = card({ id: SELF_ID, display_name: "דנה כהן", role: "owner" });

function mount(props: { selfId?: string; role?: string } = {}) {
  return render(<FloorPanel selfId={props.selfId ?? SELF_ID} role={props.role ?? "owner"} />);
}

beforeEach(() => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  vi.setSystemTime(new Date(NOW));
  getFloor.mockReset();
  startStaffBreak.mockReset();
  endStaffBreak.mockReset();
  listFloorClients.mockReset();
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

// --- F-load, F, F-self, F-empty ---------------------------------------------

describe("F-load / F / F-self / F-empty", () => {
  it("announces the first load and shows no pause control over a skeleton", async () => {
    getFloor.mockReturnValue(new Promise(() => {}));
    mount();

    expect(screen.getByTestId("floor-cue")).toHaveTextContent("טוען את רשימת הצוות…");
    // 2.2.2 is not engaged until the first payload lands: nothing is
    // auto-updating yet, so there is no content for a repaint to move.
    expect(screen.queryByRole("button", { name: /השהיה/ })).toBeNull();
  });

  it("renders a name, a role WORD and a status WORD per card", async () => {
    getFloor.mockResolvedValue(floor([ME, card()]));
    mount();

    await screen.findByText("נועה לוי");
    expect(screen.getByText("תופרת")).toBeInTheDocument();
    expect(screen.getByText("בעלת הבוטיק")).toBeInTheDocument();
    // The WORD carries the status; the colour never does.
    expect(screen.getAllByText("פנויה")).toHaveLength(2);
  });

  it("marks her own card with F51's shipped «זו את» and does not hoist it", async () => {
    // P-4: server order, never hoisted. The marker is what makes her findable
    // without reordering a list she reads positionally.
    getFloor.mockResolvedValue(floor([card(), ME]));
    mount();

    await screen.findByText("דנה כהן");
    expect(screen.getByText("זו את")).toBeInTheDocument();
    const names = screen.getAllByRole("listitem").map((li) => li.textContent ?? "");
    expect(names[0]).toContain("נועה לוי");
    expect(names[1]).toContain("דנה כהן");
  });

  it("shows the since-line only on a break, zoned to Jerusalem", async () => {
    getFloor.mockResolvedValue(
      floor([card({ status: "break", break_started_at: BREAK_BEGAN })]),
    );
    mount();

    await screen.findByText("בהפסקה");
    // 11:20 Jerusalem, NOT 08:20 UTC and not 04:20 New York.
    expect(screen.getByText(/מאז/)).toHaveTextContent("11:20");
  });

  it("renders an empty state inside the card and still shows the freshness row", async () => {
    // Unreachable in practice — the caller is herself a live staff row — but a
    // panel that has stopped updating must still be able to say so.
    getFloor.mockResolvedValue(floor([]));
    mount();

    await screen.findByText("אין נשות צוות פעילות");
    expect(screen.getByRole("button", { name: "השהיה — עדכון הצוות" })).toBeInTheDocument();
  });
});

// --- F-fail, F-stale --------------------------------------------------------

describe("F-fail / F-stale", () => {
  it("shows the OUTAGE register on a first-load failure, reusing staff.loadFailed", async () => {
    getFloor.mockRejectedValue(new ApiError(500, "SERVER_ERROR", "boom"));
    mount();

    await screen.findByText("לא הצלחנו לטעון את רשימת הצוות כרגע.");
    // F-fail renders the freshness row and its pause control: the loop is alive
    // and backing off, so a viewer who wants it to stop must be able to.
    expect(screen.getByRole("button", { name: "השהיה — עדכון הצוות" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "רענון" })).toBeInTheDocument();
  });

  it("drops «רענון» in the outage state once the loop is stopped", async () => {
    // copy.md §2 forbids this adjacency BY NAME: «רענון» beside «חידוש» is two
    // Hebrew words a hurried reader will not tell apart, and the resume control
    // is the affordance once stopped. The stale branch was already guarded; the
    // F-fail outage branch was not, and this state is new in F57 — the board
    // cannot reach it, because BoardSection renders its freshness row only when
    // rows !== null. BoardSection.test.tsx pins the same invariant for the
    // sibling component; this is its FloorPanel twin.
    getFloor.mockRejectedValue(new ApiError(500, "SERVER_ERROR", "boom"));
    mount();
    await screen.findByText("לא הצלחנו לטעון את רשימת הצוות כרגע.");
    expect(screen.getByRole("button", { name: "רענון" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /השהיה/ }));

    expect(screen.queryByRole("button", { name: "רענון" })).toBeNull();
    expect(screen.getByRole("button", { name: /חידוש/ })).toBeInTheDocument();
  });

  it("KEEPS the cards and marks them stale when a later tick fails", async () => {
    getFloor.mockResolvedValueOnce(floor([card()]));
    mount();
    await screen.findByText("נועה לוי");

    getFloor.mockRejectedValue(new ApiError(500, "SERVER_ERROR", "boom"));
    await advance(POLL_INTERVAL_MS);

    // Blanking to the outage message would throw away correct data to report a
    // network fault.
    expect(screen.getByText("נועה לוי")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText(/אין עדכון מאז/)).toBeInTheDocument());
    expect(screen.getByText("ייתכן שהמידע אינו עדכני.")).toBeInTheDocument();
  });

  it("states no retry interval anywhere on screen", async () => {
    // copy.md §0 rule 9 — the backoff falsifies any number the moment it
    // doubles, so nothing may promise one.
    getFloor.mockResolvedValueOnce(floor([card()]));
    const { container } = mount();
    await screen.findByText("נועה לוי");
    getFloor.mockRejectedValue(new ApiError(500, "SERVER_ERROR", "boom"));
    await advance(POLL_INTERVAL_MS);

    const stale = screen.getByText("ייתכן שהמידע אינו עדכני.");
    expect(stale.textContent).not.toMatch(/\d/);
    expect(container.textContent).not.toMatch(/שניות|דקה/);
  });
});

// --- F-paused, F-idle: the SC 2.2.2 mechanism -------------------------------

describe("SC 2.2.2 — the only automated coverage, because axe has no rule for it", () => {
  it("pause stops the loop and announces once; focus stays on the control", async () => {
    getFloor.mockResolvedValue(floor([card()]));
    mount();
    await screen.findByText("נועה לוי");

    const control = screen.getByRole("button", { name: "השהיה — עדכון הצוות" });
    control.focus();
    fireEvent.click(control);

    expect(screen.getByTestId("floor-cue")).toHaveTextContent("העדכון מושהה.");
    // ONE button whose name changes — never two, never aria-pressed.
    const resumed = screen.getByRole("button", { name: "חידוש — עדכון הצוות" });
    expect(resumed).toHaveTextContent("חידוש");
    expect(resumed).not.toHaveAttribute("aria-pressed");
    // It renamed, it did not unmount, so focus is still on it.
    expect(document.activeElement).toBe(resumed);

    const before = getFloor.mock.calls.length;
    await advance(POLL_INTERVAL_MS * 4);
    expect(getFloor).toHaveBeenCalledTimes(before);
  });

  it("resume fetches immediately, at the base gap, and announces", async () => {
    getFloor.mockResolvedValue(floor([card()]));
    mount();
    await screen.findByText("נועה לוי");

    fireEvent.click(screen.getByRole("button", { name: "השהיה — עדכון הצוות" }));
    const paused = getFloor.mock.calls.length;

    fireEvent.click(screen.getByRole("button", { name: "חידוש — עדכון הצוות" }));
    await waitFor(() => expect(getFloor.mock.calls.length).toBe(paused + 1));
    expect(screen.getByTestId("floor-cue")).toHaveTextContent("העדכון חודש.");
  });

  it("the idle stop fires, NAMES ITS CAUSE and names its region", async () => {
    getFloor.mockResolvedValue(floor([card()]));
    mount();
    await screen.findByText("נועה לוי");

    await advance(IDLE_STOP_MS);

    // A panel that stopped by itself and does not say why is indistinguishable
    // from a panel that broke — that difference is the whole reason F-idle and
    // F-paused are two states.
    const cue = screen.getByTestId("floor-cue");
    expect(cue).toHaveTextContent("עדכון הצוות הופסק");
    // …and it names the REGION, so it is not byte-identical to the board's.
    expect(cue).toHaveTextContent("הצוות");
    expect(screen.getByRole("button", { name: "חידוש — עדכון הצוות" })).toBeInTheDocument();
  });

  it("the pause control is the FIRST focusable thing in the panel", async () => {
    // A 2.2.2 mechanism placed after the content it governs is reachable only by
    // walking the list that is repainting under the walk.
    getFloor.mockResolvedValue(floor([card(), card({ id: "x", display_name: "רותם" })]));
    const { container } = mount();
    await screen.findByText("רותם");

    const focusable = Array.from(container.querySelectorAll("button"));
    expect(focusable[0]).toHaveAccessibleName("השהיה — עדכון הצוות");
  });
});

// --- the announced region ----------------------------------------------------

describe("the cue region", () => {
  it("does NOT change across several consecutive ticks with the cue populated", async () => {
    // ⚠ F34's F-7. A single-tick assertion passes against the broken version
    // whenever the cue starts empty, so this must POPULATE the cue first and
    // then drive several ticks. The poll may never write into a live region: a
    // status update every five seconds would announce the whole staff list
    // forever.
    getFloor.mockResolvedValue(floor([card()]));
    startStaffBreak.mockResolvedValue(
      card({ status: "break", break_started_at: BREAK_BEGAN }),
    );
    mount();
    await screen.findByText("נועה לוי");

    fireEvent.click(screen.getByRole("button", { name: /להפסקה/ }));
    await waitFor(() =>
      expect(screen.getByTestId("floor-cue")).toHaveTextContent("נרשמה הפסקה עבור"),
    );
    const populated = screen.getByTestId("floor-cue").textContent;

    await advance(POLL_INTERVAL_MS);
    await advance(POLL_INTERVAL_MS);
    await advance(POLL_INTERVAL_MS);

    expect(screen.getByTestId("floor-cue").textContent).toBe(populated);
  });

  it("names the colleague, and renders her name in a bare <bdi>", async () => {
    // A cue that cannot say WHICH person is useless exactly when it matters.
    // Bare <bdi>, never dir="ltr": forcing LTR on a Hebrew name reverses its
    // words — a bidi defect that looks deliberate.
    getFloor.mockResolvedValue(floor([card()]));
    startStaffBreak.mockResolvedValue(
      card({ status: "break", break_started_at: BREAK_BEGAN }),
    );
    mount();
    await screen.findByText("נועה לוי");

    fireEvent.click(screen.getByRole("button", { name: /להפסקה/ }));
    await waitFor(() =>
      expect(screen.getByTestId("floor-cue")).toHaveTextContent("נועה לוי"),
    );

    const bdi = screen.getByTestId("floor-cue").querySelector("bdi");
    expect(bdi).not.toBeNull();
    expect(bdi).toHaveTextContent("נועה לוי");
    expect(bdi).not.toHaveAttribute("dir");
  });

  it("puts no live attributes on the list", async () => {
    // role="log" is the tempting wrong answer — it is for append-only chat and
    // this list mutates in place.
    getFloor.mockResolvedValue(floor([card()]));
    const { container } = mount();
    await screen.findByText("נועה לוי");

    const list = container.querySelector("ul");
    expect(list).not.toHaveAttribute("role");
    expect(list).not.toHaveAttribute("aria-live");
  });

  it("leaves the freshness row readable rather than aria-hidden", async () => {
    // aria-hidden would make the panel's only honesty signal sighted-only.
    getFloor.mockResolvedValue(floor([card()]));
    mount();
    await screen.findByText("נועה לוי");

    const freshness = screen.getByText(/עודכן/);
    expect(freshness.closest("[aria-hidden]")).toBeNull();
  });
});

// --- F-busy, F-ok, F-noop, F-actfail ----------------------------------------

describe("the break toggle", () => {
  it("patches the card FROM THE RESPONSE and disables only that control", async () => {
    getFloor.mockResolvedValue(floor([ME, card()]));
    let resolve: (value: StaffCard) => void = () => {};
    startStaffBreak.mockReturnValue(
      new Promise<StaffCard>((r) => {
        resolve = r;
      }),
    );
    mount();
    await screen.findByText("נועה לוי");

    const controls = screen.getAllByRole("button", { name: /להפסקה/ });
    fireEvent.click(controls[1]);

    // One tap must not freeze the panel.
    await waitFor(() => expect(controls[1]).toBeDisabled());
    expect(controls[0]).not.toBeDisabled();

    await act(async () => {
      resolve(card({ status: "break", break_started_at: BREAK_BEGAN }));
    });
    expect(screen.getByText("בהפסקה")).toBeInTheDocument();
    expect(screen.getByText(/מאז/)).toHaveTextContent("11:20");
  });

  it("fires ONE request on a double tap", async () => {
    getFloor.mockResolvedValue(floor([card()]));
    startStaffBreak.mockReturnValue(new Promise(() => {}));
    mount();
    await screen.findByText("נועה לוי");

    const control = screen.getByRole("button", { name: /להפסקה/ });
    fireEvent.click(control);
    fireEvent.click(control);
    await waitFor(() => expect(control).toBeDisabled());

    expect(startStaffBreak).toHaveBeenCalledTimes(1);
  });

  it("announces the SAME sentence on a no-op 200 as on a write (F-noop)", async () => {
    // The server kept the first timestamp because another staffer got there
    // first. Telling her she lost a race would be telling her she was wrong
    // when she was right.
    getFloor.mockResolvedValue(floor([card()]));
    startStaffBreak.mockResolvedValue(
      card({ status: "break", break_started_at: BREAK_BEGAN }),
    );
    mount();
    await screen.findByText("נועה לוי");

    fireEvent.click(screen.getByRole("button", { name: /להפסקה/ }));
    await waitFor(() =>
      expect(screen.getByTestId("floor-cue")).toHaveTextContent(
        "נרשמה הפסקה עבור נועה לוי.",
      ),
    );
    // …and the card renders the FIRST timestamp, not this request's intent.
    expect(screen.getByText(/מאז/)).toHaveTextContent("11:20");
  });

  it("KEEPS POLLING after a failed toggle", async () => {
    // ⚠ The re-arm lives in the .finally(), and this is the test that would
    // still pass if it were dropped — and so would every other test here. A
    // rejected toggle must not park the loop, or the panel silently stops
    // converging the first time anybody acts.
    getFloor.mockResolvedValue(floor([card()]));
    startStaffBreak.mockRejectedValue(new ApiError(404, "NOT_FOUND", "gone"));
    mount();
    await screen.findByText("נועה לוי");

    fireEvent.click(screen.getByRole("button", { name: /להפסקה/ }));
    await waitFor(() => expect(screen.getByRole("alert")).toBeInTheDocument());

    const after = getFloor.mock.calls.length;
    await advance(POLL_INTERVAL_MS);
    await waitFor(() => expect(getFloor.mock.calls.length).toBeGreaterThan(after));
  });

  it("returns focus to the tapped control after a SUCCESS", async () => {
    // Button is disabled={disabled || loading}, so the browser blurred it the
    // instant the request started. Unlike F34's check-in it does not unmount —
    // it renames — so focus goes back to it.
    getFloor.mockResolvedValue(floor([card()]));
    startStaffBreak.mockResolvedValue(
      card({ status: "break", break_started_at: BREAK_BEGAN }),
    );
    mount();
    await screen.findByText("נועה לוי");

    const control = screen.getByRole("button", { name: /להפסקה/ });
    control.focus();
    fireEvent.click(control);

    // ⚠ REPRODUCE THE BLUR, or this test cannot fail. jsdom does NOT blur a
    // focused element when it becomes `disabled`, and HTMLElement.blur() returns
    // early on a disabled one — so without this the button stays focused for the
    // whole request, the restore effect's `activeElement === body` guard is never
    // true, and the assertion below is satisfied purely by the button renaming in
    // place. A real browser blurs it. Verified: with these three lines the test
    // reddens when the restore effect is deleted; without them it stays green.
    const heading = screen.getByRole("heading", { level: 2 });
    heading.focus();
    heading.blur();
    expect(document.activeElement).toBe(document.body);

    await waitFor(() =>
      expect(document.activeElement).toHaveAccessibleName("חזרה — נועה לוי"),
    );
  });

  it("suppresses every tick while a toggle is in flight", async () => {
    // Pins FloorPanel's `mutationsRef.current > 0 -> "suppressed"` branch, which
    // had NO coverage anywhere: deleting those three lines left all 484 tests
    // green. usePoll's own "suppressed" case cannot cover it — in the hook,
    // "suppressed" and `void` take the identical empty branch, so the mechanism
    // only exists here.
    getFloor.mockResolvedValue(floor([card()]));
    startStaffBreak.mockReturnValue(new Promise(() => {}));
    mount();
    await screen.findByText("נועה לוי");

    fireEvent.click(screen.getByRole("button", { name: /להפסקה/ }));
    await waitFor(() => expect(startStaffBreak).toHaveBeenCalled());
    const before = getFloor.mock.calls.length;

    // ⚠ The reachable path is the VISIBILITYCHANGE refetch, not the timer:
    // `toggle` calls poll.clearTick() so no timer is armed during a mutation,
    // which is why a timer-only assertion here is vacuous. TWO callers invoke
    // the tick DIRECTLY rather than through the timer — the visibilitychange
    // handler and poll.refresh() behind «רענון» — so either can arrive
    // mid-mutation, and `mutationsRef.current > 0 -> "suppressed"` is what stops
    // it repainting the row under the request. The guard lives in tick() rather
    // than at either call site precisely because there are two.
    await act(async () => {
      Object.defineProperty(document, "hidden", { configurable: true, value: true });
      document.dispatchEvent(new Event("visibilitychange"));
      Object.defineProperty(document, "hidden", { configurable: true, value: false });
      document.dispatchEvent(new Event("visibilitychange"));
    });

    expect(getFloor).toHaveBeenCalledTimes(before);
    await advance(POLL_INTERVAL_MS * 3);
    expect(getFloor).toHaveBeenCalledTimes(before);
  });

  it("hands focus back when a successful poll clears the focused in-card alert", async () => {
    // ⚠ REGRESSION. The alert is focused by the failure effect; the very next
    // successful tick calls setCardError(null) and unmounts it — five seconds
    // later, with NO user action. Removing a focused node drops activeElement to
    // <body>, so her next Tab restarts at the skip link. WCAG 2.4.3, and the
    // departing-card rescue cannot cover it because a 5xx leaves the colleague
    // in the list.
    getFloor.mockResolvedValue(floor([card()]));
    startStaffBreak.mockRejectedValue(new ApiError(500, "SERVER_ERROR", "boom"));
    mount();
    await screen.findByText("נועה לוי");

    const control = screen.getByRole("button", { name: /להפסקה/ });
    control.focus();
    fireEvent.click(control);
    await waitFor(() => expect(document.activeElement).toBe(screen.getByRole("alert")));

    // The next tick succeeds and removes the alert.
    await advance(POLL_INTERVAL_MS);
    await waitFor(() => expect(screen.queryByRole("alert")).toBeNull());

    expect(document.activeElement).not.toBe(document.body);
    expect(document.activeElement).toHaveAccessibleName("להפסקה — נועה לוי");
  });

  it("moves focus to the in-card alert after a FAILURE", async () => {
    // ⚠ THE FAILURE PATH IS THE ONE THAT GETS FORGOTTEN. This exact bug class
    // shipped TWICE in this repo (F56 on the storefront, F34 on the board) and
    // axe walked past it both times, because axe cannot see a focus move that
    // never happened.
    getFloor.mockResolvedValue(floor([card()]));
    startStaffBreak.mockRejectedValue(new ApiError(404, "NOT_FOUND", "gone"));
    mount();
    await screen.findByText("נועה לוי");

    const control = screen.getByRole("button", { name: /להפסקה/ });
    control.focus();
    fireEvent.click(control);

    await waitFor(() => {
      const alert = screen.getByRole("alert");
      expect(alert).toHaveTextContent("אשת הצוות הזו כבר לא פעילה.");
      expect(document.activeElement).toBe(alert);
    });
  });

  it("puts the 404 alert INSIDE the card, not at panel level", async () => {
    // A panel-level error names no colleague.
    getFloor.mockResolvedValue(floor([ME, card()]));
    startStaffBreak.mockRejectedValue(new ApiError(404, "NOT_FOUND", "gone"));
    mount();
    await screen.findByText("נועה לוי");

    fireEvent.click(screen.getAllByRole("button", { name: /להפסקה — נועה לוי/ })[0]);
    await waitFor(() => expect(screen.getByRole("alert")).toBeInTheDocument());

    const item = screen.getByRole("alert").closest("li");
    expect(item).not.toBeNull();
    expect(within(item as HTMLElement).getByText("נועה לוי")).toBeInTheDocument();
  });
});

// --- F-401, F-403, and P-6 ---------------------------------------------------

describe("the terminal states", () => {
  it("a tick's 401 stops the loop and clears the cards", async () => {
    getFloor.mockResolvedValueOnce(floor([card()]));
    mount();
    await screen.findByText("נועה לוי");

    getFloor.mockRejectedValue(new ApiError(401, "NOT_AUTHENTICATED", "gone"));
    await advance(POLL_INTERVAL_MS);

    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent("תוקף החיבור פג."),
    );
    // A dead session cannot vouch for the cards.
    expect(screen.queryByText("נועה לוי")).toBeNull();

    const after = getFloor.mock.calls.length;
    await advance(POLL_INTERVAL_MS * 4);
    expect(getFloor).toHaveBeenCalledTimes(after);
  });

  it("a tick's 403 stops the loop with a DIFFERENT sentence naming no role", async () => {
    getFloor.mockResolvedValueOnce(floor([card()]));
    mount();
    await screen.findByText("נועה לוי");

    getFloor.mockRejectedValue(new ApiError(403, "NOT_AUTHORIZED", "no"));
    await advance(POLL_INTERVAL_MS);

    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent("אין הרשאה לצפות ברשימת הצוות"),
    );
    // For the three floor roles this sentence is the whole product going dark,
    // so it may not teach the permission model (copy.md §0 rule 10).
    const alert = screen.getByRole("alert").textContent ?? "";
    for (const word of ["תופרת", "קבלה", "יועצת מכירות", "אחראית משמרת"]) {
      expect(alert).not.toContain(word);
    }
  });

  it("a TOGGLE's 403 is terminal for the whole panel (P-6)", async () => {
    // The realistic cause is a mid-shift demotion between the last tick and the
    // tap. The alternative — an in-card alert plus a loop that keeps polling
    // with a role the server just refused — is the panel disagreeing with
    // itself for five seconds and then doing the same thing anyway.
    getFloor.mockResolvedValue(floor([card()]));
    startStaffBreak.mockRejectedValue(new ApiError(403, "NOT_AUTHORIZED", "no"));
    mount();
    await screen.findByText("נועה לוי");

    fireEvent.click(screen.getByRole("button", { name: /להפסקה/ }));

    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent("אין הרשאה לצפות ברשימת הצוות"),
    );
    expect(screen.queryByText("נועה לוי")).toBeNull();
  });

  it("a TOGGLE's 404 is NOT terminal — the panel survives", async () => {
    // A colleague vanishing is a fact about her, not about the viewer's access.
    // That asymmetry is the point.
    getFloor.mockResolvedValue(floor([card()]));
    startStaffBreak.mockRejectedValue(new ApiError(404, "NOT_FOUND", "gone"));
    mount();
    await screen.findByText("נועה לוי");

    fireEvent.click(screen.getByRole("button", { name: /להפסקה/ }));
    await waitFor(() => expect(screen.getByRole("alert")).toBeInTheDocument());

    expect(screen.getByText("נועה לוי")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "השהיה — עדכון הצוות" })).toBeInTheDocument();
  });
});

// --- which control exists: D6's two axes, rendered ---------------------------

describe("the control matrix is cosmetics over the server's check", () => {
  it("a non-elevated staffer sees a control on HER card only", async () => {
    // On a colleague's card she sees a name, a role and a status and NOTHING
    // else — no disabled button, no lock glyph, no «אין לך הרשאה» line, no
    // tooltip. A disabled control with no explanation is worse than an absent
    // one, and an explanation would teach the permission model on a screen she
    // opens fifty times a shift.
    getFloor.mockResolvedValue(
      floor([card({ id: SELF_ID, display_name: "דנה כהן" }), card()]),
    );
    mount({ role: "seamstress" });
    await screen.findByText("נועה לוי");

    const controls = screen.getAllByRole("button", { name: /להפסקה/ });
    expect(controls).toHaveLength(1);
    expect(controls[0]).toHaveAccessibleName("להפסקה — דנה כהן");
    // Asserted AS COSMETICS: no explanatory text stands in for the missing one.
    const colleague = screen.getByText("נועה לוי").closest("li") as HTMLElement;
    expect(within(colleague).queryByRole("button")).toBeNull();
    expect(colleague.textContent).not.toContain("הרשאה");
  });

  it.each(["owner", "shift_manager"])("an elevated %s sees a control on every card", async (role) => {
    getFloor.mockResolvedValue(
      floor([card({ id: SELF_ID, display_name: "דנה כהן" }), card()]),
    );
    mount({ role });
    await screen.findByText("נועה לוי");

    expect(screen.getAllByRole("button", { name: /להפסקה/ })).toHaveLength(2);
  });
});

// --- F36: the card's third status and the occupancy line ---------------------

function cardOf(name: string): HTMLElement {
  return screen.getByText(name).closest("li") as HTMLElement;
}

describe("the third card status (F36)", () => {
  it("an OCCUPIED card reads «תפוסה», her room and her client — never «פנויה»", async () => {
    // AC22, and the one a reviewer should look for. The shipped Badge was a
    // BINARY ternary, so `status: "occupied"` fell to its else branch and
    // printed «פנויה» about a woman standing in room 2 — one word away from the
    // lie this whole feature exists to prevent.
    getFloor.mockResolvedValue(floor([card({ status: "occupied", occupancy: occupancy() })]));
    mount();
    await screen.findByText("נועה לוי");

    expect(screen.getByText("תפוסה")).toBeInTheDocument();
    expect(screen.queryByText("פנויה")).toBeNull();

    const item = cardOf("נועה לוי");
    expect(within(item).getByText("חדר 2")).toBeInTheDocument();
    expect(within(item).getByText("מיכל")).toBeInTheDocument();
    // Computed against the envelope's server_now, so only the DELTA of a
    // boutique tablet's clock is trusted and never its absolute value.
    expect(item.textContent).toContain("כבר 42 דק'");
  });

  it("renders the holder's role as muted words and never a second Badge", async () => {
    // Deck P-2. Two pills in 295px teaches the reader to scan colours instead
    // of words, which is how a status vocabulary dies. The card's ONE Badge is
    // the status; the role is muted words in a bare <bdi>.
    getFloor.mockResolvedValue(floor([card({ status: "occupied", occupancy: occupancy() })]));
    mount();
    await screen.findByText("נועה לוי");

    const item = cardOf("נועה לוי");
    const role = within(item).getByText("תופרת");
    expect(role.tagName).toBe("BDI");
    expect(role).not.toHaveAttribute("dir");
    expect(role.closest("p")).toHaveClass("text-ink-muted");
    // Badge is the only rounded-full span in the tree.
    expect(item.querySelectorAll("span.rounded-full")).toHaveLength(1);
  });

  it("labels the client on the occupancy line, and says so when there is none", async () => {
    // DC-11. A bare name one line under another bare name, separated by a
    // character most screen readers do not voice, is not a labelled value —
    // rooms.clientLabel is what makes the middle fragment readable.
    getFloor.mockResolvedValue(
      floor([
        card({ status: "occupied", occupancy: occupancy() }),
        card({
          id: SELF_ID,
          display_name: "רותם",
          status: "occupied",
          // The DEFAULT render for any claim made without a booking — a
          // staffer prepping a room, a swept booking, an erased customer.
          occupancy: occupancy({ room_label: "הבמה", client_label: null }),
        }),
      ]),
    );
    mount();
    await screen.findByText("רותם");

    expect(within(cardOf("נועה לוי")).getByText("לקוחה")).toBeInTheDocument();
    const anonymous = cardOf("רותם");
    expect(anonymous.textContent).toContain("ללא לקוחה מקושרת");
    expect(within(anonymous).queryByText("לקוחה")).toBeNull();
    expect(within(anonymous).getByText("הבמה")).toBeInTheDocument();
  });

  it("says «זה עתה» for the first minute rather than «כבר 0 דק'»", async () => {
    // `created_at` comes from the DATABASE clock and `server_now` from the
    // service's Python one, so assignedAt > serverNow is representable and a
    // raw subtraction can go negative. Math.max(0, …) plus this string removes
    // both, and «זה עתה» is a fact rather than a clamp artefact.
    getFloor.mockResolvedValue(
      floor([
        card({
          status: "occupied",
          occupancy: occupancy({ assigned_at: "2026-08-04T11:08:00Z" }),
        }),
      ]),
    );
    mount();
    await screen.findByText("נועה לוי");

    const item = cardOf("נועה לוי");
    expect(item.textContent).toContain("זה עתה");
    expect(item.textContent).not.toContain("כבר");
  });

  it("renders no occupancy line at all on a free card", async () => {
    getFloor.mockResolvedValue(floor([card()]));
    mount();
    await screen.findByText("נועה לוי");

    const item = cardOf("נועה לוי");
    expect(item.textContent).not.toContain("לקוחה");
    expect(item.textContent).not.toContain("כבר");
  });
});

// --- deck F-2: the boolean F36 breaks if nobody looks ------------------------

describe("deck F-2 — occupied wins the status, break_started_at owns the break", () => {
  // The rarest card in the product, and the only place a screen can tell a
  // shift manager that a break was never closed: occupied AND still on a break.
  // No shipped block constructs it, which is exactly why each of the three
  // sites below needs its own named test — nothing else in this suite goes red
  // when `onBreak` is derived from `status`.
  const forgotten = () =>
    floor([
      card({ status: "occupied", break_started_at: BREAK_BEGAN, occupancy: occupancy() }),
    ]);

  it("keeps the since-line on a staffer who is occupied AND still on a break", async () => {
    // MUTATION: revert the since-line guard to `card.status === "break"`. The
    // one signal that makes a forgotten break legible then vanishes exactly
    // when it has lasted longest (F57's F-6).
    getFloor.mockResolvedValue(forgotten());
    mount();
    await screen.findByText("נועה לוי");

    expect(screen.getByText(/מאז/)).toHaveTextContent("11:20");
  });

  it("offers «חזרה» and calls endStaffBreak, never «להפסקה»", async () => {
    // ⚠ MUTATION: revert toggle()'s `onBreak` to `card.status === "break"`.
    // Without this she can NEVER end that break from this screen: the control
    // reads «להפסקה» and calls startStaffBreak, the tap is a 200 no-op keeping
    // the FIRST timestamp, the cue confirms a break was recorded, and it stays
    // that way until she releases the room.
    getFloor.mockResolvedValue(forgotten());
    endStaffBreak.mockResolvedValue(card({ status: "available", break_started_at: null }));
    mount();
    await screen.findByText("נועה לוי");

    const control = screen.getByRole("button", { name: "חזרה — נועה לוי" });
    expect(control).toHaveTextContent("חזרה");
    expect(screen.queryByRole("button", { name: /להפסקה/ })).toBeNull();

    fireEvent.click(control);
    await waitFor(() => expect(endStaffBreak).toHaveBeenCalledWith(OTHER_ID));
    expect(startStaffBreak).not.toHaveBeenCalled();
  });

  it("still reads «תפוסה» and not «בהפסקה» while that break is open", async () => {
    // MUTATION: revert the Badge to the shipped binary ternary — «בהפסקה» wins
    // and the card stops saying she is in a room. `status` is a DISPLAY
    // PRECEDENCE and occupied beats break, on the wire and on the render.
    getFloor.mockResolvedValue(forgotten());
    mount();
    await screen.findByText("נועה לוי");

    expect(screen.getByText("תפוסה")).toBeInTheDocument();
    expect(screen.queryByText("בהפסקה")).toBeNull();
    expect(screen.queryByText("פנויה")).toBeNull();
  });
});

// --- accessibility -----------------------------------------------------------

describe("accessibility", () => {
  it("names each break control with its visible label PLUS the person", async () => {
    // Five buttons all named «להפסקה» is a screen-reader dead end, and the name
    // starts with the visible label so WCAG 2.5.3 label-in-name holds.
    getFloor.mockResolvedValue(floor([card()]));
    mount();
    await screen.findByText("נועה לוי");

    const control = screen.getByRole("button", { name: /להפסקה/ });
    expect(control).toHaveAccessibleName("להפסקה — נועה לוי");
    expect(control).toHaveTextContent("להפסקה");
  });

  it("renders exactly one h2 and exactly one h3 — the rooms subsection", async () => {
    // ⚠ THE ONE SHIPPED EXPECTATION F36 EDITS, and it is edited because its
    // PREMISE was falsified rather than because the extraction drifted. F57's
    // deck justified having no h3 with «the panel has no groups»; F36 gives it
    // one, and the h3 is also the rooms panel's focus-rescue target (deck F-1,
    // DC-10), so it renders in EVERY state including the empty one — which is
    // exactly what this fixture, with its defaulted `rooms: []`, exercises.
    // Nothing else in this file moves.
    getFloor.mockResolvedValue(floor([card()]));
    mount();
    await screen.findByText("נועה לוי");

    expect(screen.getAllByRole("heading", { level: 2 })).toHaveLength(1);
    expect(screen.getAllByRole("heading", { level: 3 })).toHaveLength(1);
    expect(screen.getByRole("heading", { level: 3 })).toHaveTextContent("חדרי מדידה");
  });

  it("passes axe with zero violations", async () => {
    // ⚠ EXPLICITLY NOT SUFFICIENT. axe has NO rule for SC 2.2.2, so the pause
    // and idle assertions above are the only automated coverage of a Level A
    // criterion that IS 5568 makes legally binding here. These must not be cut
    // as redundant with this row, now or in any later tidy-up.
    getFloor.mockResolvedValue(
      floor([
        card({ id: SELF_ID, display_name: "דנה כהן", role: "owner" }),
        card({ status: "break", break_started_at: BREAK_BEGAN }),
      ]),
    );
    const { container } = mount();
    await screen.findByText("נועה לוי");

    const results = await run(container);
    expect(results.violations).toEqual([]);
  });

  it("passes axe on the occupied card too, break included", async () => {
    // The occupied render is new markup — a third Badge word and a three-
    // fragment occupancy line with two <bdi>s in it — so the shipped axe row
    // above cannot speak for it. Same caveat: axe has NO rule for SC 2.2.2 and
    // no way to see a focus move that never happened.
    getFloor.mockResolvedValue(
      floor([
        card({ id: SELF_ID, display_name: "דנה כהן", role: "owner" }),
        card({ status: "occupied", break_started_at: BREAK_BEGAN, occupancy: occupancy() }),
        card({
          id: "66666666-6666-6666-6666-666666666666",
          display_name: "רותם",
          status: "occupied",
          occupancy: occupancy({ room_label: "הבמה", client_label: null }),
        }),
      ]),
    );
    const { container } = mount();
    await screen.findByText("רותם");

    const results = await run(container);
    expect(results.violations).toEqual([]);
  });
});
