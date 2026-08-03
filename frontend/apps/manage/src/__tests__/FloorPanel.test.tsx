import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { run } from "axe-core";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import "../i18n";
import type { FloorResponse, StaffCard } from "../api";
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
    },
  };
});

const { api, ApiError } = await import("../api");
const getFloor = vi.mocked(api.getFloor);
const startStaffBreak = vi.mocked(api.startStaffBreak);
const endStaffBreak = vi.mocked(api.endStaffBreak);

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
    ...overrides,
  };
}

function floor(staff: StaffCard[]): FloorResponse {
  return { staff };
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

  it("renders exactly one h2 and no h3", async () => {
    getFloor.mockResolvedValue(floor([card()]));
    mount();
    await screen.findByText("נועה לוי");

    expect(screen.getAllByRole("heading", { level: 2 })).toHaveLength(1);
    expect(screen.queryAllByRole("heading", { level: 3 })).toHaveLength(0);
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
});
