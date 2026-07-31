import type { ReactNode } from "react";
import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { run } from "axe-core";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import "../i18n";
import type { OwnerBookingDetail, OwnerBookingListResponse, OwnerBookingRow } from "../api";
import { BoardSection } from "../components/BoardSection";

vi.mock("../api", async () => {
  const actual = await vi.importActual<typeof import("../api")>("../api");
  return {
    ApiError: actual.ApiError,
    errorMessage: actual.errorMessage,
    api: {
      listBookings: vi.fn(),
      checkInBooking: vi.fn(),
      undoBookingCheckIn: vi.fn(),
    },
  };
});

const { api, ApiError } = await import("../api");
const listBookings = vi.mocked(api.listBookings);
const checkInBooking = vi.mocked(api.checkInBooking);
const undoBookingCheckIn = vi.mocked(api.undoBookingCheckIn);

// 11:07Z is 14:07 in Jerusalem (IDT, UTC+3) and 07:07 in New York — and the
// test script pins TZ=America/New_York, so an unzoned read prints 07:07 and
// every freshness assertion below would fail loudly rather than quietly.
const NOW = "2026-08-04T11:07:00Z";
const POLL = 5_000;
const IDLE = 600_000;

function row(overrides: Partial<OwnerBookingRow> = {}): OwnerBookingRow {
  return {
    id: "b1",
    starts_at: "2026-08-04T06:30:00Z", // 09:30 Jerusalem — before "now"
    status: "confirmed",
    attendance_confirmed_at: null,
    checked_in_at: null,
    customer_name: "מיכל לוי",
    appointment_type_name: "מדידה ראשונה",
    dress_name: "שמלת אלמה",
    ...overrides,
  };
}

function detail(overrides: Partial<OwnerBookingDetail> = {}): OwnerBookingDetail {
  return {
    ...row(),
    customer_phone: "+972501234567",
    notes: null,
    dress_id: "d1",
    dress_size: "36",
    seat_index: 1,
    created_at: "2026-08-01T06:12:00Z",
    terms_version_accepted: 3,
    terms_accepted_at: "2026-08-01T06:12:00Z",
    cancelled_at: null,
    cancelled_by: null,
    manage_link_issued: true,
    ...overrides,
  };
}

function day(items: OwnerBookingRow[], total = items.length): OwnerBookingListResponse {
  return { items, total, offset: 0, limit: 50 };
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((res) => {
    resolve = res;
  });
  return { promise, resolve };
}

// Every timer advance goes through act(): the poll settles in a microtask and
// paints, and an unwrapped advance would report the assertion against the
// previous render.
async function advance(ms: number) {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });
}

async function flush() {
  await advance(0);
}

async function click(element: HTMLElement) {
  await act(async () => {
    fireEvent.click(element);
    await vi.advanceTimersByTimeAsync(0);
  });
}

async function mountBoard(first: OwnerBookingListResponse = day([row()])) {
  listBookings.mockResolvedValue(first);
  const view = render(<BoardSection />);
  await flush();
  return view;
}

// BoardSection renders inside ConsoleShell's <main>, which owns the console's
// single sr-only <h1>. The axe harness reproduces that frame rather than
// scanning a headless fragment.
function renderInShell(node: ReactNode) {
  return render(
    <main>
      <h1 className="sr-only">ניהול הבוטיק</h1>
      {node}
    </main>,
  );
}

function setHidden(hidden: boolean) {
  Object.defineProperty(document, "hidden", { configurable: true, get: () => hidden });
}

async function fireVisibility(hidden: boolean) {
  setHidden(hidden);
  await act(async () => {
    document.dispatchEvent(new Event("visibilitychange"));
    await vi.advanceTimersByTimeAsync(0);
  });
}

function checkInButton() {
  return screen.getByRole("button", { name: /^הגיעה/ });
}

function pauseButton() {
  return screen.getByRole("button", { name: "השהיה — עדכון הלוח" });
}

function resumeButton() {
  return screen.getByRole("button", { name: "חידוש — עדכון הלוח" });
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.useFakeTimers();
  vi.setSystemTime(new Date(NOW));
  setHidden(false);
});

afterEach(() => {
  vi.useRealTimers();
  setHidden(false);
});

// --- D4, the six poll mechanisms. Each has its own named assertion and none of
// --- them is covered by any of the others.

describe("D4(1) — the loop is schedule-after-settle, never setInterval", () => {
  it("issues exactly one request per tick and never two in flight", async () => {
    // The next tick is armed from the PREVIOUS request's .finally(), so at most
    // one poll is in flight per tab by construction — there is nothing to abort
    // and no in-flight flag to get wrong.
    listBookings.mockReturnValue(new Promise(() => {}));
    render(<BoardSection />);
    await flush();
    expect(listBookings).toHaveBeenCalledTimes(1);

    await advance(POLL * 4);
    expect(listBookings).toHaveBeenCalledTimes(1);
  });

  it("beats once per interval once the request settles", async () => {
    await mountBoard();
    expect(listBookings).toHaveBeenCalledTimes(1);
    await advance(POLL);
    expect(listBookings).toHaveBeenCalledTimes(2);
    await advance(POLL);
    expect(listBookings).toHaveBeenCalledTimes(3);
  });
});

describe("D4(2) — one monotonic generation", () => {
  it("discards a poll response issued before a check-in and keeps the mutation's value", async () => {
    await mountBoard(day([row()]));

    // The tick at +5s is issued BEFORE the tap and will answer the pre-tap
    // truth. Hold it open across the mutation.
    const pending = deferred<OwnerBookingListResponse>();
    listBookings.mockReturnValueOnce(pending.promise);
    await advance(POLL);
    expect(listBookings).toHaveBeenCalledTimes(2);

    checkInBooking.mockResolvedValue(detail({ checked_in_at: "2026-08-04T06:24:00Z" }));
    await click(checkInButton());
    expect(screen.getByTestId("board-arrival")).toHaveTextContent("נרשמה הגעה · 09:24");

    await act(async () => {
      pending.resolve(day([row({ checked_in_at: null })]));
      await vi.advanceTimersByTimeAsync(0);
    });

    // The tap bumped the generation, so the older answer can never repaint the
    // row it did not know about.
    expect(screen.getByTestId("board-arrival")).toHaveTextContent("נרשמה הגעה · 09:24");
  });
});

describe("D4(3a) — document.hidden", () => {
  it("pauses the loop while the tab is hidden", async () => {
    await mountBoard();
    await fireVisibility(true);
    await advance(POLL * 3);
    expect(listBookings).toHaveBeenCalledTimes(1);
  });

  it("fetches IMMEDIATELY on the way back to visible, not after an interval", async () => {
    await mountBoard();
    await fireVisibility(true);
    await advance(POLL * 3);
    expect(listBookings).toHaveBeenCalledTimes(1);

    // The board is stale by however long it was hidden; five more seconds of a
    // wrong board is the worst possible moment to add.
    await fireVisibility(false);
    expect(listBookings).toHaveBeenCalledTimes(2);
  });
});

describe("D4(3b) — 401 is terminal", () => {
  it("stops the loop on a 401 and renders the session-ended alert", async () => {
    await mountBoard();
    listBookings.mockRejectedValue(new ApiError(401, "NOT_AUTHENTICATED", "Not authenticated."));
    await advance(POLL);
    expect(listBookings).toHaveBeenCalledTimes(2);

    expect(screen.getByRole("alert")).toHaveTextContent("תוקף החיבור פג. צריך להתחבר מחדש.");
    expect(screen.getByRole("button", { name: "רענון הדף" })).toBeInTheDocument();
    // A dead session cannot vouch for the rows, and leaving them under a "you
    // are logged out" message invites a tap that will 401 too.
    expect(screen.queryByRole("list")).toBeNull();

    await advance(POLL * 5);
    expect(listBookings).toHaveBeenCalledTimes(2);
  });
});

describe("D4(3c) — 403 is terminal too, and it is a SEPARATE case from the 401", () => {
  it("stops the loop on a 403 and renders the access-ended alert", async () => {
    // The mid-shift demotion. It arrives by a different code path — the session
    // resolves fine and RoleGate raises — and a board that stopped only on 401
    // would keep polling a revoked role at 0.2 req/s forever while the demotion
    // had no visible effect, silently defeating F31's "a demotion bites on the
    // very next request" on the one screen that keeps making requests after a
    // revocation.
    await mountBoard();
    listBookings.mockRejectedValue(new ApiError(403, "NOT_AUTHORIZED", "Not authorized."));
    await advance(POLL);

    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent(
      "אין הרשאה לצפות בלוח כרגע. לבירור אפשר לפנות לבעלת הבוטיק.",
    );
    expect(screen.getByRole("button", { name: "רענון הדף" })).toBeInTheDocument();
    expect(screen.queryByRole("list")).toBeNull();

    await advance(POLL * 5);
    expect(listBookings).toHaveBeenCalledTimes(2);
  });

  it("says nothing about the role — the server's 403 body is generic by design", async () => {
    await mountBoard();
    listBookings.mockRejectedValue(new ApiError(403, "NOT_AUTHORIZED", "Not authorized."));
    await advance(POLL);

    const text = screen.getByRole("alert").textContent ?? "";
    for (const word of ["אחראית משמרת", "תפקיד", "בוטלו"]) {
      expect(text).not.toContain(word);
    }
  });
});

describe("D4(4a) — the board is not optimistic", () => {
  it("patches the row from the server's response, never from the tap", async () => {
    await mountBoard();
    checkInBooking.mockResolvedValue(
      detail({ checked_in_at: "2026-08-04T06:24:00Z", customer_name: "מיכל לוי" }),
    );

    await click(checkInButton());

    expect(checkInBooking).toHaveBeenCalledWith("b1");
    // 06:24Z is 09:24 in Jerusalem — the server's value, rendered as words plus
    // a time and never as a tint, a dot or a check glyph.
    expect(screen.getByTestId("board-arrival")).toHaveTextContent("נרשמה הגעה · 09:24");
    expect(screen.queryByRole("button", { name: /^הגיעה/ })).toBeNull();
    expect(screen.getByRole("button", { name: /^ביטול הרישום/ })).toBeInTheDocument();
  });

  it("disables the tapped control in flight, so a double tap fires one request", async () => {
    await mountBoard();
    const pending = deferred<OwnerBookingDetail>();
    checkInBooking.mockReturnValueOnce(pending.promise);

    const button = checkInButton();
    await click(button);
    expect(button).toBeDisabled();
    expect(button).toHaveAttribute("aria-busy", "true");

    await click(button);
    expect(checkInBooking).toHaveBeenCalledTimes(1);

    await act(async () => {
      pending.resolve(detail({ checked_in_at: "2026-08-04T06:24:00Z" }));
      await vi.advanceTimersByTimeAsync(0);
    });
  });

  it("leaves every OTHER row's control live while one is in flight", async () => {
    await mountBoard(day([row({ id: "b1" }), row({ id: "b2", customer_name: "נועה כהן" })]));
    checkInBooking.mockReturnValueOnce(deferred<OwnerBookingDetail>().promise);

    const buttons = screen.getAllByRole("button", { name: /^הגיעה/ });
    await click(buttons[0]);
    // The board is not a form and one tap must not freeze the shift.
    expect(buttons[0]).toBeDisabled();
    expect(buttons[1]).toBeEnabled();
  });

  it("issues no tick while a mutation is in flight", async () => {
    await mountBoard();
    const pending = deferred<OwnerBookingDetail>();
    checkInBooking.mockReturnValueOnce(pending.promise);
    await click(checkInButton());
    const before = listBookings.mock.calls.length;

    await advance(POLL * 3);
    // The row cannot be repainted underneath the request.
    expect(listBookings).toHaveBeenCalledTimes(before);

    await act(async () => {
      pending.resolve(detail({ checked_in_at: "2026-08-04T06:24:00Z" }));
      await vi.advanceTimersByTimeAsync(0);
    });
  });
});

describe("D4(4b) — the suppressed tick is re-armed from the mutation's .finally()", () => {
  it("re-arms after a SUCCESSFUL check-in", async () => {
    await mountBoard();
    checkInBooking.mockResolvedValue(detail({ checked_in_at: "2026-08-04T06:24:00Z" }));
    await click(checkInButton());
    const after = listBookings.mock.calls.length;

    await advance(POLL);
    expect(listBookings).toHaveBeenCalledTimes(after + 1);
  });

  it("re-arms after a FAILED check-in", async () => {
    // The arming lives in the mutation's .finally(), never in its success path:
    // a rejected check-in must not park the loop either. Without this the board
    // silently stops converging the first time a staffer acts, and every other
    // test in this file still passes.
    await mountBoard();
    checkInBooking.mockRejectedValue(
      new ApiError(409, "BOOKING_TRANSITION_INVALID", "Invalid transition."),
    );
    await click(checkInButton());
    expect(screen.getByRole("alert")).toHaveTextContent(
      "מצב התור השתנה. השורה תתוקן בעדכון הבא.",
    );
    const after = listBookings.mock.calls.length;

    await advance(POLL);
    expect(listBookings).toHaveBeenCalledTimes(after + 1);
  });
});

describe("D4(6) — the failure backoff", () => {
  it("stretches the interval on consecutive failures, caps it, and resets on the first success", async () => {
    // There is no server-side ceiling on this path — D3 declines a read limiter
    // — so the throttle is the client's, and a fleet of loyal boards retrying
    // every five seconds through an outage is the load the server can least
    // take.
    await mountBoard();
    listBookings.mockRejectedValue(new ApiError(503, "UNAVAILABLE", "Service unavailable."));

    await advance(POLL);
    expect(listBookings).toHaveBeenCalledTimes(2);
    await advance(9_999);
    expect(listBookings).toHaveBeenCalledTimes(2);
    await advance(1);
    expect(listBookings).toHaveBeenCalledTimes(3); // 10s
    await advance(20_000);
    expect(listBookings).toHaveBeenCalledTimes(4); // 20s
    await advance(40_000);
    expect(listBookings).toHaveBeenCalledTimes(5); // 40s
    await advance(60_000);
    expect(listBookings).toHaveBeenCalledTimes(6); // capped
    await advance(59_999);
    expect(listBookings).toHaveBeenCalledTimes(6); // it did not double past the cap
    await advance(1);
    expect(listBookings).toHaveBeenCalledTimes(7);

    listBookings.mockResolvedValue(day([row()]));
    await advance(60_000);
    expect(listBookings).toHaveBeenCalledTimes(8);
    await advance(POLL);
    expect(listBookings).toHaveBeenCalledTimes(9); // back to the base interval
  });

  it("treats a 401 as terminal rather than as a backoff case", async () => {
    await mountBoard();
    listBookings.mockRejectedValue(new ApiError(401, "NOT_AUTHENTICATED", "Not authenticated."));
    await advance(POLL);
    await advance(60_000 * 3);
    expect(listBookings).toHaveBeenCalledTimes(2);
  });
});

// --- D14, WCAG 2.0 SC 2.2.2 Pause, Stop, Hide (Level A, inside AA, and AA is a
// --- LEGAL bar here). axe has NO rule for 2.2.2, so these assertions are the
// --- only automated coverage of the criterion anywhere in the product and must
// --- not be dropped as redundant with the axe row below.

describe("D14 — the pause control", () => {
  it("stops the loop", async () => {
    await mountBoard();
    await click(pauseButton());
    const after = listBookings.mock.calls.length;

    await advance(POLL * 4);
    expect(listBookings).toHaveBeenCalledTimes(after);
    expect(screen.getByTestId("board-updated")).toHaveTextContent("מושהה · עודכן 14:07");
    expect(screen.getByTestId("board-body")).toHaveTextContent(
      "העדכון מושהה. הלוח לא יתעדכן עד לחידוש.",
    );
  });

  it("fetches immediately on resume, before the interval elapses", async () => {
    await mountBoard();
    await click(pauseButton());
    const after = listBookings.mock.calls.length;

    // Waiting out an interval after being asked to resume would make the
    // control feel broken on the one press that has to feel decisive.
    await click(resumeButton());
    expect(listBookings).toHaveBeenCalledTimes(after + 1);
  });

  it("resets a backed-off interval on resume", async () => {
    await mountBoard();
    listBookings.mockRejectedValue(new ApiError(503, "UNAVAILABLE", "down"));
    await advance(POLL);
    await advance(10_000);
    await advance(20_000); // the interval is now 40s

    await click(pauseButton());
    listBookings.mockResolvedValue(day([row()]));
    await click(resumeButton());
    const after = listBookings.mock.calls.length;

    // A resume is a fresh user intent; inheriting a 60-second gap would look
    // like a control that did not work.
    await advance(POLL);
    expect(listBookings).toHaveBeenCalledTimes(after + 1);
  });

  it("is ONE button whose name changes, never two and never aria-pressed", async () => {
    await mountBoard();
    const pause = pauseButton();
    expect(pause).not.toHaveAttribute("aria-pressed");
    expect(screen.queryByRole("button", { name: "חידוש — עדכון הלוח" })).toBeNull();

    await click(pause);
    expect(screen.queryByRole("button", { name: "השהיה — עדכון הלוח" })).toBeNull();
    expect(resumeButton()).toBeInTheDocument();
  });

  it("carries the 44px floor, the focus ring and a text label — never colour alone", async () => {
    await mountBoard();
    const pause = pauseButton();
    // size="md" -> min-h-11 = 44px. sm is min-h-9 = 36px, under the floor.
    expect(pause).toHaveClass("min-h-11");
    expect(pause).toHaveClass("focus-visible:outline-focus");
    expect(pause).toHaveTextContent("השהיה");

    await click(pause);
    // Three text signals for the paused state: the word «מושהה», the body line
    // and the control's own label flipping. No icon anywhere.
    expect(screen.getByTestId("board-updated")).toHaveTextContent("מושהה");
    expect(resumeButton()).toHaveTextContent("חידוש");
  });

  it("is the FIRST control inside the board, before any row", async () => {
    // A 2.2.2 mechanism placed after the auto-updating content it governs would
    // be reachable only by walking forty tab stops on a list repainting
    // underneath the walk — the exact situation the criterion exists to let a
    // user escape.
    const { container } = await mountBoard(day([row({ id: "b1" }), row({ id: "b2" })]));
    const buttons = Array.from(container.querySelectorAll("button"));
    expect(buttons[0]).toBe(pauseButton());
  });

  it("keeps focus on the control across the press — it renames, it does not unmount", async () => {
    await mountBoard();
    const pause = pauseButton();
    pause.focus();
    await click(pause);
    expect(document.activeElement).toBe(resumeButton());
  });
});

describe("D14 — the idle stop", () => {
  it("stops the loop after ten minutes with no interaction and names the cause", async () => {
    await mountBoard();
    await advance(IDLE);
    const after = listBookings.mock.calls.length;

    await advance(POLL * 4);
    expect(listBookings).toHaveBeenCalledTimes(after);
    // A board that stopped BY ITSELF and does not say why is indistinguishable
    // from a board that broke.
    expect(screen.getByTestId("board-body")).toHaveTextContent(
      "העדכון הופסק אחרי 10 דקות ללא פעילות.",
    );
    expect(screen.getByTestId("board-updated")).toHaveTextContent("מושהה · עודכן");
  });

  it("resumes in one tap", async () => {
    await mountBoard();
    await advance(IDLE);
    const after = listBookings.mock.calls.length;

    await click(resumeButton());
    expect(listBookings).toHaveBeenCalledTimes(after + 1);
  });

  it("is reset by an interaction, so it does not fire under a working shift", async () => {
    await mountBoard();
    for (let i = 0; i < 4; i += 1) {
      await advance(IDLE / 2);
      await act(async () => {
        window.dispatchEvent(new Event("pointerdown"));
        await vi.advanceTimersByTimeAsync(0);
      });
    }
    expect(screen.queryByTestId("board-body")).toBeNull();
    expect(screen.getByTestId("board-updated")).not.toHaveTextContent("מושהה");
  });
});

// --- D11, the live-region rule. A role="status" update every five seconds is
// --- an AA failure in practice however green the automated check comes back.

describe("D11 — the announced region", () => {
  it("does not change across CONSECUTIVE poll ticks with the cue already populated", async () => {
    // F-7: assigning an identical string to a live region still replaces the
    // Text node, so a single-tick assertion passes against the broken version
    // whenever the cue starts empty. Several ticks, cue populated, zero records.
    await mountBoard();
    checkInBooking.mockResolvedValue(detail({ checked_in_at: "2026-08-04T06:24:00Z" }));
    await click(checkInButton());
    expect(screen.getByTestId("board-cue")).toHaveTextContent("נרשמה הגעה עבור מיכל לוי.");

    const observer = new MutationObserver(() => {});
    observer.observe(screen.getByTestId("board-cue"), {
      childList: true,
      characterData: true,
      subtree: true,
    });
    const before = listBookings.mock.calls.length;
    await advance(POLL);
    await advance(POLL);
    await advance(POLL);
    // The ticks really happened — otherwise this asserts nothing.
    expect(listBookings).toHaveBeenCalledTimes(before + 3);
    expect(observer.takeRecords()).toEqual([]);
    observer.disconnect();
  });

  it("changes on a check-in, on an undo and on a pause", async () => {
    await mountBoard();
    const cue = screen.getByTestId("board-cue");

    checkInBooking.mockResolvedValue(detail({ checked_in_at: "2026-08-04T06:24:00Z" }));
    await click(checkInButton());
    expect(cue).toHaveTextContent("נרשמה הגעה עבור מיכל לוי.");

    undoBookingCheckIn.mockResolvedValue(detail({ checked_in_at: null }));
    await click(screen.getByRole("button", { name: /^ביטול הרישום/ }));
    expect(cue).toHaveTextContent("הרישום בוטל עבור מיכל לוי.");

    await click(pauseButton());
    expect(cue).toHaveTextContent("העדכון מושהה.");

    await click(resumeButton());
    expect(cue).toHaveTextContent("העדכון חודש.");
  });

  it("announces the first load and nothing else while loading", async () => {
    listBookings.mockReturnValue(new Promise(() => {}));
    render(<BoardSection />);
    await flush();
    expect(screen.getByRole("status")).toHaveTextContent("טוען את לוח היום…");
    expect(screen.queryByRole("list")).toBeNull();
  });

  it("moves focus to the cue after a check-in, since the tapped control unmounts", async () => {
    await mountBoard();
    checkInBooking.mockResolvedValue(detail({ checked_in_at: "2026-08-04T06:24:00Z" }));
    await click(checkInButton());
    // Without this, focus drops to <body> (WCAG 2.4.3).
    expect(document.activeElement).toBe(screen.getByTestId("board-cue"));
  });

  it("keeps the freshness row readable and OUT of every live region", async () => {
    // The deck's F-1, accepted into the spec's a11y floor: aria-hidden here
    // would make the board's only honesty signal sighted-only, so a screen
    // reader user could never learn the board stopped updating.
    await mountBoard();
    const freshness = screen.getByTestId("board-freshness");
    expect(freshness).not.toHaveAttribute("aria-hidden");
    expect(freshness.closest("[aria-live]")).toBeNull();
    expect(freshness.closest('[role="status"]')).toBeNull();
    expect(freshness.closest('[role="alert"]')).toBeNull();
    expect(freshness).toHaveTextContent("עודכן 14:07");
  });

  it("leaves the list itself with no live attributes at all", async () => {
    await mountBoard();
    const list = screen.getByRole("list");
    expect(list).not.toHaveAttribute("aria-live");
    expect(list).not.toHaveAttribute("role");
  });
});

// --- D12, the Jerusalem day.

describe("D12 — the Jerusalem date is recomputed every tick", () => {
  it("refetches for the new day when the date rolls under an unattended tablet", async () => {
    // 20:59:57Z is 23:59:57 in Jerusalem. A counter tablet crosses midnight;
    // todayJerusalem() captured at mount would keep asking for yesterday.
    vi.setSystemTime(new Date("2026-08-04T20:59:57Z"));
    await mountBoard(day([]));
    expect(listBookings).toHaveBeenLastCalledWith({
      date: "2026-08-04",
      offset: 0,
      limit: 50,
    });
    expect(screen.getByTestId("board-day")).toHaveTextContent("היום · 4.8.2026");

    await advance(POLL);
    expect(listBookings).toHaveBeenLastCalledWith({
      date: "2026-08-05",
      offset: 0,
      limit: 50,
    });
    expect(screen.getByTestId("board-day")).toHaveTextContent("היום · 5.8.2026");
  });
});

// --- The states the deck's §4 owns. The list may not shrink.

describe("the board's states", () => {
  it("B-load — a Skeleton and no freshness row, because nothing is fresh yet", async () => {
    listBookings.mockReturnValue(new Promise(() => {}));
    render(<BoardSection />);
    await flush();
    expect(screen.queryByTestId("board-freshness")).toBeNull();
    expect(screen.getByTestId("board-day")).toBeInTheDocument();
  });

  it("B-empty — an EmptyState with no CTA, and a freshness row that still reads 0/0", async () => {
    await mountBoard(day([]));
    expect(screen.getByText("אין תורים היום")).toBeInTheDocument();
    // An empty board that has stopped updating must still be able to say so.
    expect(screen.getByTestId("board-summary")).toHaveTextContent("הגיעו 0/0");
    // The owner cannot create a booking, so an action prompt would point at
    // nothing. The only button left is the pause control.
    expect(screen.getAllByRole("button")).toHaveLength(1);
  });

  it("B-fail — a FIRST fetch failure shows the outage register plus a retry", async () => {
    listBookings.mockRejectedValue(new ApiError(503, "UNAVAILABLE", "down"));
    render(<BoardSection />);
    await flush();

    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent("לא הצלחנו לטעון את הלוח כרגע.");
    // An outage, not a fault of hers: muted, never text-danger.
    expect(alert).toHaveClass("text-ink-muted");
    // Unlike F15's list this screen has no date control to re-poke, so the
    // retry is a real affordance rather than a second tab stop for one act.
    expect(screen.getByRole("button", { name: "רענון" })).toBeInTheDocument();
    expect(screen.queryByRole("list")).toBeNull();
  });

  it("B-stale — a failed poll with rows on screen KEEPS the rows and marks them stale", async () => {
    await mountBoard();
    expect(screen.getByTestId("board-updated")).toHaveTextContent("עודכן 14:07");

    listBookings.mockRejectedValue(new ApiError(503, "UNAVAILABLE", "down"));
    await advance(POLL);

    // Blanking to the outage message would throw away correct data to report a
    // network fault.
    expect(screen.getByText("מיכל לוי")).toBeInTheDocument();
    const updated = screen.getByTestId("board-updated");
    expect(updated).toHaveTextContent("אין עדכון מאז 14:07");
    // P-6: correct-looking rows beside a grey notice are what gets scanned past.
    expect(updated).toHaveClass("text-warning-text");
    expect(screen.getByTestId("board-body")).toHaveTextContent("ייתכן שהמידע אינו עדכני.");
    expect(screen.getByRole("button", { name: "רענון" })).toBeInTheDocument();
  });

  it("B-stale — the retry fetches now and clears the stale copy on success", async () => {
    await mountBoard();
    listBookings.mockRejectedValue(new ApiError(503, "UNAVAILABLE", "down"));
    await advance(POLL);

    listBookings.mockResolvedValue(day([row()]));
    const after = listBookings.mock.calls.length;
    await click(screen.getByRole("button", { name: "רענון" }));
    expect(listBookings).toHaveBeenCalledTimes(after + 1);
    expect(screen.getByTestId("board-updated")).toHaveTextContent("עודכן 14:07");
  });

  it("B-paused beats B-stale in the freshness slot, and the two retry controls never share a line", async () => {
    await mountBoard();
    listBookings.mockRejectedValue(new ApiError(503, "UNAVAILABLE", "down"));
    await advance(POLL);
    expect(screen.getByTestId("board-updated")).toHaveTextContent("אין עדכון מאז");

    await click(pauseButton());
    // A stopped loop cannot fail a tick, so the stop is the operative cause and
    // the resume control is the operative remedy.
    expect(screen.getByTestId("board-updated")).toHaveTextContent("מושהה · עודכן 14:07");
    expect(screen.queryByRole("button", { name: "רענון" })).toBeNull();
  });

  it("B-trunc — the truncation line appears only when total > items.length", async () => {
    await mountBoard(day([row()], 1));
    expect(screen.queryByTestId("board-truncated")).toBeNull();

    await mountBoard(day([row({ id: "b1" }), row({ id: "b2" })], 60));
    // A hidden bride is the one failure a board may not have, so the truncation
    // is stated rather than absorbed.
    expect(screen.getAllByTestId("board-truncated")[0]).toHaveTextContent(
      "מוצגים 2 התורים הראשונים של היום",
    );
  });

  it("B-actfail — a 409 renders INSIDE the row, in the fix-this register", async () => {
    await mountBoard(day([row({ id: "b1" }), row({ id: "b2", customer_name: "נועה כהן" })]));
    checkInBooking.mockRejectedValue(
      new ApiError(409, "BOOKING_TRANSITION_INVALID", "Invalid transition."),
    );

    await click(screen.getAllByRole("button", { name: /^הגיעה/ })[0]);

    // A page-level error on a forty-row board names no bride.
    const item = screen.getByText("מיכל לוי").closest("li");
    expect(item).not.toBeNull();
    const alert = within(item as HTMLElement).getByRole("alert");
    expect(alert).toHaveTextContent("מצב התור השתנה. השורה תתוקן בעדכון הבא.");
    expect(alert).toHaveClass("text-danger");
  });

  it("B-404 — an unmapped code falls through to the shared helper unchanged", async () => {
    await mountBoard();
    checkInBooking.mockRejectedValue(new ApiError(404, "NOT_FOUND", "Booking not found."));
    await click(checkInButton());
    expect(screen.getByRole("alert")).toHaveTextContent("Booking not found.");
  });

  it("B-noop — a repeat check-in renders identically, because it IS the outcome she wanted", async () => {
    // The server keeps the FIRST timestamp and the row renders it. Telling her
    // she lost a race would be telling her she was wrong when she was right.
    await mountBoard();
    checkInBooking.mockResolvedValue(detail({ checked_in_at: "2026-08-04T06:20:00Z" }));
    await click(checkInButton());
    expect(screen.getByTestId("board-arrival")).toHaveTextContent("נרשמה הגעה · 09:20");
    expect(screen.getByTestId("board-cue")).toHaveTextContent("נרשמה הגעה עבור מיכל לוי.");
  });
});

// --- The row: one action, the control matrix, and the bidi rules.

describe("the row", () => {
  it("is not a button and carries exactly one control", async () => {
    // A row that is itself a button cannot contain a button — nested
    // interactive content is an HTML and an AT defect, not a style preference.
    await mountBoard(day([row({ id: "b1" }), row({ id: "b2", customer_name: "נועה כהן" })]));
    for (const item of screen.getAllByRole("listitem")) {
      expect(item.tagName).toBe("LI");
      expect(within(item).getAllByRole("button")).toHaveLength(1);
    }
  });

  it("renders only the operation the server will accept", async () => {
    await mountBoard(
      day([
        row({ id: "b1", status: "confirmed", customer_name: "א" }),
        row({ id: "b2", status: "cancelled", customer_name: "ב" }),
        row({ id: "b3", status: "no_show", customer_name: "ג" }),
        row({ id: "b4", status: "completed", customer_name: "ד" }),
      ]),
    );
    // Rendering four buttons where three answer 409 is a trap; a disabled button
    // with no explanation is worse than an absent one.
    expect(screen.getAllByRole("button", { name: /^הגיעה/ })).toHaveLength(1);
  });

  it("offers the undo on a row whose status moved on, because the server takes no guard", async () => {
    await mountBoard(
      day([
        row({ id: "b1", status: "no_show", checked_in_at: "2026-08-04T06:24:00Z" }),
        row({ id: "b2", status: "cancelled", checked_in_at: "2026-08-04T06:25:00Z", customer_name: "נועה כהן" }),
      ]),
    );
    // D5: a status transition never touches checked_in_at, so these rows are
    // real and their undo must work.
    expect(screen.getAllByRole("button", { name: /^ביטול הרישום/ })).toHaveLength(2);
    // P-3: never time-boxed. A control that disappeared after five minutes
    // would be a lie the API contradicts.
    expect(screen.getByText("לא הגיעה")).toBeInTheDocument();
    expect(screen.getAllByTestId("board-arrival")).toHaveLength(2);
  });

  it("keeps cancelled rows in the list, as «תורים» one nav item away does", async () => {
    await mountBoard(day([row({ status: "cancelled" })]));
    expect(screen.getByText("מיכל לוי")).toBeInTheDocument();
    expect(screen.getByText("בוטל")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^הגיעה/ })).toBeNull();
  });

  it("isolates numeric runs LTR and leaves Hebrew free text in a BARE bdi", async () => {
    await mountBoard(day([row({ checked_in_at: "2026-08-04T06:24:00Z" })]));

    const time = screen.getByText("09:30");
    expect(time.tagName).toBe("BDI");
    expect(time).toHaveAttribute("dir", "ltr");

    // dir="ltr" on a Hebrew name is itself a bidi defect, and it looks
    // deliberate, which is what makes it the worse one.
    for (const text of ["מיכל לוי", "מדידה ראשונה", "שמלת אלמה"]) {
      const node = screen.getByText(text);
      expect(node.tagName).toBe("BDI");
      expect(node).not.toHaveAttribute("dir");
    }
  });

  it("keeps exactly one Badge per row — arrival is words, never a second chip", async () => {
    await mountBoard(
      day([row({ checked_in_at: "2026-08-04T06:24:00Z", attendance_confirmed_at: NOW })]),
    );
    const item = screen.getByRole("listitem");
    expect(within(item).getAllByTestId("board-status")).toHaveLength(1);
    expect(within(item).getByTestId("board-arrival")).toBeInTheDocument();
    expect(within(item).getByText(/אישרה הגעה/)).toBeInTheDocument();
  });

  it("carries the 44px floor and a per-person accessible name on both controls", async () => {
    await mountBoard(day([row(), row({ id: "b2", checked_in_at: "2026-08-04T06:24:00Z" })]));
    const checkIn = checkInButton();
    const undo = screen.getByRole("button", { name: /^ביטול הרישום/ });
    for (const control of [checkIn, undo]) {
      expect(control).toHaveClass("min-h-11");
      expect(control).toHaveClass("focus-visible:outline-focus");
    }
    // Forty buttons all named «הגיעה» is a screen-reader dead end, and the name
    // starts with the visible label so WCAG 2.5.3 label-in-name holds.
    expect(checkIn).toHaveAttribute("aria-label", "הגיעה — מיכל לוי, 09:30");
    expect(undo).toHaveAttribute("aria-label", "ביטול הרישום — מיכל לוי, 09:30");
  });

  it("keeps the server's order and never re-sorts a checked-in row", async () => {
    // Bands would move the row you just tapped into another band, on the one
    // screen whose entire budget goes on not moving under you (P-4).
    await mountBoard(
      day([
        row({ id: "b1", starts_at: "2026-08-04T06:30:00Z", customer_name: "א" }),
        row({ id: "b2", starts_at: "2026-08-04T07:00:00Z", customer_name: "ב" }),
        row({ id: "b3", starts_at: "2026-08-04T07:30:00Z", customer_name: "ג" }),
      ]),
    );
    checkInBooking.mockResolvedValue(
      detail({ id: "b2", customer_name: "ב", checked_in_at: "2026-08-04T06:55:00Z" }),
    );
    await click(screen.getAllByRole("button", { name: /^הגיעה/ })[1]);

    const names = screen
      .getAllByRole("listitem")
      .map((item) => item.getAttribute("data-booking-id"));
    expect(names).toEqual(["b1", "b2", "b3"]);
  });

  it("renders the «עכשיו» divider between past and future, hidden from AT", async () => {
    await mountBoard(
      day([
        row({ id: "b1", starts_at: "2026-08-04T06:30:00Z", customer_name: "א" }),
        row({ id: "b2", starts_at: "2026-08-04T11:30:00Z", customer_name: "ב" }),
      ]),
    );
    const divider = screen.getByTestId("board-now");
    // A clock-derived visual landmark. Unhidden it would inject a changing
    // string into the middle of the list on every tick — the D11 hazard through
    // the back door.
    expect(divider).toHaveAttribute("aria-hidden", "true");
    expect(divider).toHaveTextContent("עכשיו 14:07");
  });

  it("omits the divider when it would mark nothing", async () => {
    await mountBoard(day([row({ starts_at: "2026-08-04T06:30:00Z" })]));
    expect(screen.queryByTestId("board-now")).toBeNull();
  });
});

describe("the ratio", () => {
  it("counts arrivals over the day's rows as one LTR run", async () => {
    await mountBoard(
      day([
        row({ id: "b1", checked_in_at: "2026-08-04T06:24:00Z" }),
        row({ id: "b2" }),
        row({ id: "b3" }),
      ]),
    );
    const ratio = screen.getByText("1/3");
    expect(ratio.tagName).toBe("BDI");
    expect(ratio).toHaveAttribute("dir", "ltr");
    expect(screen.getByTestId("board-summary")).toHaveTextContent("הגיעו 1/3");
  });
});

describe("F-8 — a tick may not repaint under a finger", () => {
  it("holds one repaint on pointerdown and can never stall the board", async () => {
    const { container } = await mountBoard();
    const board = container.firstElementChild as HTMLElement;
    const after = listBookings.mock.calls.length;

    await act(async () => {
      fireEvent.pointerDown(board);
      await vi.advanceTimersByTimeAsync(0);
    });
    // An arrival line appearing on an earlier row grows it ~26px and slides
    // every control below it, so a finger already travelling toward row 9 lands
    // on the row above or on nothing.
    await advance(POLL);
    expect(listBookings).toHaveBeenCalledTimes(after);

    // The loop keeps its own beat underneath: the hold is consumed by the tick
    // it skipped, so a lost pointerup costs one interval and never the board.
    await advance(POLL);
    expect(listBookings).toHaveBeenCalledTimes(after + 1);
  });
});

describe("a row that leaves the day while it holds focus", () => {
  it("is kept and says why, rather than dropping focus to <body>", async () => {
    await mountBoard(
      day([row({ id: "b1" }), row({ id: "b2", customer_name: "נועה כהן" })]),
    );
    const control = screen.getAllByRole("button", { name: /^הגיעה/ })[0];
    control.focus();

    // The only way a row leaves the day is a reschedule to another date;
    // cancelled rows stay.
    listBookings.mockResolvedValue(day([row({ id: "b2", customer_name: "נועה כהן" })]));
    await advance(POLL);

    // Replacing the control unmounts the focused element, so keeping the row is
    // only half the repair — focus moves to the note in the same row rather
    // than to <body>, which is where it would otherwise land for something the
    // user did not do.
    expect(screen.getByTestId("board-moved")).toHaveTextContent("התור הועבר לתאריך אחר");
    expect(document.activeElement).toBe(screen.getByTestId("board-moved"));
    expect(screen.getAllByRole("listitem")).toHaveLength(2);

    // Removed on the first tick after focus moves.
    pauseButton().focus();
    await advance(POLL);
    expect(screen.queryByTestId("board-moved")).toBeNull();
    expect(screen.getAllByRole("listitem")).toHaveLength(1);
  });
});

describe("BoardSection accessibility", () => {
  it("passes axe with zero violations on the loaded board", async () => {
    // EXPLICITLY NOT SUFFICIENT: axe has no SC 2.2.2 rule, so the pause and
    // idle assertions above are the only automated coverage of a Level A
    // criterion and must survive any later tidy-up of "redundant" a11y tests.
    vi.useRealTimers();
    listBookings.mockResolvedValue(
      day([
        row({ id: "b1", attendance_confirmed_at: NOW }),
        row({ id: "b2", customer_name: "נועה כהן", checked_in_at: "2026-08-04T06:24:00Z" }),
        row({ id: "b3", customer_name: "שיר אברהם", starts_at: "2026-08-04T11:30:00Z" }),
      ], 60),
    );
    const { container } = renderInShell(<BoardSection />);
    await screen.findByText("מיכל לוי");

    const results = await run(container);
    expect(results.violations).toEqual([]);
  }, 20000);

  it("passes axe with zero violations on the empty day", async () => {
    vi.useRealTimers();
    listBookings.mockResolvedValue(day([]));
    const { container } = renderInShell(<BoardSection />);
    await screen.findByText("אין תורים היום");

    const results = await run(container);
    expect(results.violations).toEqual([]);
  }, 20000);

  it("puts the section under a single h2 with no skipped level", async () => {
    await mountBoard();
    const headings = screen.getAllByRole("heading");
    expect(headings).toHaveLength(1);
    expect(headings[0].tagName).toBe("H2");
    expect(headings[0]).toHaveTextContent("לוח היום");
  });
});
