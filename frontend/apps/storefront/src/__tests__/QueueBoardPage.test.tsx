import { StrictMode } from "react";
import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { run } from "axe-core";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { BoutiqueResponse, QueueBoardEntry, QueueBoardView } from "../api";
import { StorefrontLayout } from "../components/StorefrontLayout";
import i18n from "../i18n";
import { QueueBoardPage } from "../routes/QueueBoardPage";

// Spread the real module so ApiError keeps its real implementation. This page
// makes no terminal decision from an error — that is the point of half these
// tests — but the 404 and 429 cases are only meaningful if the errors are real.
vi.mock("../api", async () => {
  const actual = await vi.importActual<typeof import("../api")>("../api");
  return {
    ...actual,
    api: { ...actual.api, getQueueBoard: vi.fn() },
    getBoutiqueOnce: vi.fn(),
  };
});

const { ApiError, api, getBoutiqueOnce } = await import("../api");
const getQueueBoard = vi.mocked(api.getQueueBoard);
const loadBoutique = vi.mocked(getBoutiqueOnce);

const POLL = 5_000;

// 11:07Z is 14:07 in Jerusalem (IDT, UTC+3) and 07:07 in New York — and
// package.json pins TZ=America/New_York for the test run, so a formatter built
// without a timeZone prints 07:07 and the freshness assertion fails loudly. On a
// television nobody has ever set the clock on, that is not a hypothetical.
const NOW = "2026-08-04T11:07:00Z";
const NOW_JERUSALEM = "14:07";

// Every live region in this repo is a bare role="status" with NO aria-live
// attribute, and closest() matches ATTRIBUTES rather than implicit ARIA — so
// closest('[aria-live]') alone returns null even from INSIDE one and could not
// fail. All three selectors, with a negative control below proving it bites.
const ANNOUNCED = '[role="status"],[role="alert"],[aria-live]';

// A34 / SC 1.4.4. The exact class strings, pinned as constants so a silent
// collapse back to text-sm is a diff in one place. Axe measures no font size and
// has no rule for any of this.
const POSITION_SCALE = "text-[clamp(2.5rem,2.5rem+3.3vh,9rem)]";
const NAME_SCALE = "text-[clamp(2rem,2rem+2.5vh,7rem)]";
const HEADING_SCALE = "text-[clamp(1.5rem,1.5rem+1.8vh,4rem)]";
// W-5: deliberately the SMALLEST text on a screen designed for four metres. A
// control the room can read is a control the room will eventually press, and a
// wall frozen by a passer-by reads as live to the next woman who sits down.
// A34 must not promote it.
const SMALL_SCALE = "text-[clamp(1rem,1rem+0.8vh,2rem)]";

function boutique(): BoutiqueResponse {
  return {
    name: "בוטיק אלמה",
    essence: null,
    description: null,
    phone: "052-1234567",
    address: "דיזנגוף 100, תל אביב",
    maps_url: null,
    instagram: "alma.bridal",
    hours: [],
    exceptions: [],
  };
}

const NAMES = ["נועה", "מיכל", "שירה", "תמר", "יעל"];

function entry(position: number, overrides: Partial<QueueBoardEntry> = {}): QueueBoardEntry {
  return {
    position,
    first_name: NAMES[(position - 1) % NAMES.length],
    called: false,
    ...overrides,
  };
}

function board(count = 3, overrides: Partial<QueueBoardView> = {}): QueueBoardView {
  const entries = Array.from({ length: count }, (_, index) => entry(index + 1));
  return { entries, waiting_total: entries.length, ...overrides };
}

function t(key: string, options?: Record<string, unknown>): string {
  return i18n.t(key, options);
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((res) => {
    resolve = res;
  });
  return { promise, resolve };
}

// Every timer advance goes through act(): the poll settles in a microtask and
// paints, and an unwrapped advance reports the assertion against the previous
// render.
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

function renderPage() {
  return render(
    <StorefrontLayout>
      <QueueBoardPage />
    </StorefrontLayout>,
  );
}

async function mountPage() {
  const view = renderPage();
  await flush();
  return view;
}

function section(): HTMLElement {
  return screen.getByTestId("queue-board");
}

function freshnessLine(): HTMLElement {
  return screen.getByTestId("queue-board-freshness");
}

function cueRegion(): HTMLElement {
  return screen.getByTestId("queue-board-cue");
}

function rows(): HTMLElement[] {
  return screen.queryAllByTestId("queue-board-row");
}

function pauseButton(): HTMLElement {
  return screen.getByRole("button", { name: t("checkin.pause") });
}

function resumeButton(): HTMLElement {
  return screen.getByRole("button", { name: t("checkin.resume") });
}

function observe(node: Node): MutationObserver {
  const observer = new MutationObserver(() => undefined);
  observer.observe(node, { subtree: true, childList: true, characterData: true, attributes: true });
  return observer;
}

beforeEach(() => {
  vi.clearAllMocks();
  window.history.replaceState(null, "", "/queue");
  document.title = "";
  loadBoutique.mockResolvedValue(boutique());
  getQueueBoard.mockResolvedValue(board());
  vi.useFakeTimers();
  vi.setSystemTime(new Date(NOW));
  setHidden(false);
});

afterEach(() => {
  vi.useRealTimers();
  setHidden(false);
});

// --- D9, the poll copied from the shipped QueuePositionPage. Each mechanism has
// --- its own named assertion; none of them is covered by any of the others.

describe("D9 — the poll", () => {
  it("issues exactly one request per tick and never two in flight", async () => {
    // The next tick is armed from the PREVIOUS request's .finally(), so at most
    // one poll is in flight per tab BY CONSTRUCTION — nothing to abort, no
    // in-flight flag to keep right.
    getQueueBoard.mockReturnValue(new Promise(() => undefined));
    renderPage();
    await flush();
    expect(getQueueBoard).toHaveBeenCalledTimes(1);

    await advance(POLL * 4);
    expect(getQueueBoard).toHaveBeenCalledTimes(1);
  });

  it("beats once per interval once the request settles", async () => {
    await mountPage();
    expect(getQueueBoard).toHaveBeenCalledTimes(1);
    await advance(POLL);
    expect(getQueueBoard).toHaveBeenCalledTimes(2);
    await advance(POLL);
    expect(getQueueBoard).toHaveBeenCalledTimes(3);
  });

  it("the poll stops when the page unmounts mid-request", async () => {
    // clearTick() ALONE does not do it. It cancels the timer armed right now;
    // the arming site is a .finally(), which runs AFTER this cleanup when a
    // request is in flight, and nothing in tick -> load -> finally -> schedule
    // touches React state — so the orphan cannot be broken by unmounting. This
    // has shipped as a defect twice in this repo.
    const pending = deferred<QueueBoardView>();
    getQueueBoard.mockReturnValue(pending.promise);
    const view = renderPage();
    await flush();
    expect(getQueueBoard).toHaveBeenCalledTimes(1);

    view.unmount();
    await act(async () => {
      pending.resolve(board());
      await vi.advanceTimersByTimeAsync(0);
    });

    await advance(POLL * 10);
    expect(getQueueBoard).toHaveBeenCalledTimes(1);
  });

  it("the poll survives a StrictMode remount", async () => {
    // React 19's StrictMode performs setup -> cleanup -> setup on purpose. The
    // cleanup sets runningRef false and NOTHING else sets it true except
    // resume(), so without `runningRef.current = true` as the FIRST line of the
    // mount effect the loop is permanently dead behind a pause button that still
    // looks like it works.
    //
    // On a wall that symptom is a television showing a CORRECT board frozen at
    // the moment of mount, with nobody in the room to notice. It is the worst
    // instance of this bug in the product, and it is inherited from a file that
    // shipped it.
    render(
      <StrictMode>
        <StorefrontLayout>
          <QueueBoardPage />
        </StorefrontLayout>
      </StrictMode>,
    );
    await flush();
    const afterMount = getQueueBoard.mock.calls.length;
    // The double-invoked effect is what makes this test non-vacuous: two loads
    // at mount is the evidence the cycle actually ran.
    expect(afterMount).toBeGreaterThan(1);

    await advance(POLL);
    expect(getQueueBoard.mock.calls.length).toBeGreaterThan(afterMount);
  });

  it("stops while the tab is hidden and fetches at once when it comes back", async () => {
    // Browsers throttle background timers to >=1/minute, so an unpaused loop
    // would look live while being a minute stale. On a kiosk this is also the
    // one state with no automatic recovery (Risk 10) — accepted as a ceiling,
    // mitigated by the checklist line "a single full-screen tab, no blanking".
    await mountPage();
    expect(getQueueBoard).toHaveBeenCalledTimes(1);

    await fireVisibility(true);
    await advance(POLL * 4);
    expect(getQueueBoard).toHaveBeenCalledTimes(1);

    await fireVisibility(false);
    expect(getQueueBoard).toHaveBeenCalledTimes(2);
  });

  it("doubles the interval 5s -> 60s on failures, holds the cap, and resets on a success", async () => {
    getQueueBoard.mockRejectedValue(new Error("network"));
    await mountPage();
    expect(getQueueBoard).toHaveBeenCalledTimes(1);

    for (const [index, gap] of [10_000, 20_000, 40_000, 60_000].entries()) {
      await advance(gap - 1);
      expect(getQueueBoard).toHaveBeenCalledTimes(index + 1);
      await advance(1);
      expect(getQueueBoard).toHaveBeenCalledTimes(index + 2);
    }

    // The cap holds rather than doubling to 120s.
    await advance(60_000);
    expect(getQueueBoard).toHaveBeenCalledTimes(6);

    getQueueBoard.mockResolvedValue(board());
    await advance(60_000);
    expect(getQueueBoard).toHaveBeenCalledTimes(7);
    await advance(POLL);
    expect(getQueueBoard).toHaveBeenCalledTimes(8);
  });
});

// --- D9's deliberate divergence from the file the builder had open beside them.

describe("D9 — the loop has NO terminal", () => {
  it("a 404 does not stop the loop", async () => {
    // A 404 here is TENANT_NOT_FOUND — a suspended or misconfigured tenant, a
    // fact about the SERVER — not a dead link the user holds. The position page
    // stops because her ticket is gone and no retry brings it back; this page
    // has nothing to lose and NOBODY AT THE KEYBOARD. A wall screen that gives
    // up permanently needs a human to notice and reload, and there is none.
    getQueueBoard.mockRejectedValue(new ApiError(404, "TENANT_NOT_FOUND", "No active boutique."));
    await mountPage();
    expect(getQueueBoard).toHaveBeenCalledTimes(1);
    expect(screen.getByText(t("queueBoard.loadFailed"))).toBeInTheDocument();

    // Ten intervals at the backing-off ladder: 5+10+20+40+60*n. Well past the
    // cap, so the calls keep coming at one a minute forever.
    await advance(POLL);
    await advance(10_000);
    await advance(20_000);
    await advance(40_000);
    await advance(60_000 * 6);
    expect(getQueueBoard.mock.calls.length).toBeGreaterThan(9);
  });

  it("a 429 does not stop the loop either", async () => {
    await mountPage();
    getQueueBoard.mockRejectedValue(
      new ApiError(429, "TOO_MANY_ATTEMPTS", "Too many attempts. Try again later."),
    );
    await advance(POLL);
    expect(getQueueBoard).toHaveBeenCalledTimes(2);

    getQueueBoard.mockResolvedValue(board(2));
    await advance(10_000);
    expect(getQueueBoard).toHaveBeenCalledTimes(3);
    expect(rows()).toHaveLength(2);
  });

  it("a failed tick after a good load keeps the rows on screen and only relabels them", async () => {
    // Blanking a correct board because one request failed throws away the only
    // thing the room came to read. A flooder holding the budget spent can make
    // the wall STALE; he cannot make it wrong, and that bound is only worth
    // anything because the freshness line is room-legible.
    await mountPage();
    expect(rows()).toHaveLength(3);

    getQueueBoard.mockRejectedValue(new ApiError(503, "UNKNOWN", "down"));
    await advance(POLL);
    expect(rows()).toHaveLength(3);
    expect(rows()[0]).toHaveTextContent(NAMES[0]);
    expect(freshnessLine()).toHaveTextContent(t("checkin.staleAt"));
    expect(screen.queryByText(t("queueBoard.loadFailed"))).toBeNull();
  });

  it("announces the error arm ONCE across several consecutive failures", async () => {
    // The loop has no terminal, so W-fail can re-render every 60 seconds for
    // hours. React's reconciler leaves the identical Text node untouched, so
    // nothing re-announces — asserted as one announcement rather than as one
    // failure and none.
    getQueueBoard.mockRejectedValue(new ApiError(503, "UNKNOWN", "down"));
    await mountPage();
    const alert = screen.getByRole("alert");

    const observer = observe(alert);
    // Walking the ladder, because a failed first request has already doubled the
    // gap to 10s — advancing by POLL here would assert against ticks that never
    // happened and the observation would be vacuous.
    await advance(10_000);
    await advance(20_000);
    await advance(40_000);
    expect(getQueueBoard).toHaveBeenCalledTimes(4);
    expect(observer.takeRecords()).toEqual([]);
    observer.disconnect();
  });
});

// --- D11, SC 2.2.2 (Level A) — a LEGAL bar here, and axe has NO rule for any of
// --- it. This block is the ONLY automated coverage of the criterion on this
// --- screen and must not be dropped as redundant with the axe row below.

describe("the wall board carries a working pause control (SC 2.2.2)", () => {
  it("stops the loop when pressed, and resuming fetches before an interval elapses", async () => {
    await mountPage();
    expect(getQueueBoard).toHaveBeenCalledTimes(1);

    await click(pauseButton());
    await advance(POLL * 6);
    expect(getQueueBoard).toHaveBeenCalledTimes(1);

    await click(resumeButton());
    expect(getQueueBoard).toHaveBeenCalledTimes(2);
  });

  it("resets a backed-off gap on resume, so the control cannot look like it failed", async () => {
    await mountPage();
    getQueueBoard.mockRejectedValue(new Error("network"));
    await advance(POLL);
    await advance(10_000);
    await advance(20_000);
    expect(getQueueBoard).toHaveBeenCalledTimes(4);

    getQueueBoard.mockResolvedValue(board());
    await click(pauseButton());
    await click(resumeButton());
    expect(getQueueBoard).toHaveBeenCalledTimes(5);

    // Back at the base interval rather than inheriting the 80s gap.
    await advance(POLL);
    expect(getQueueBoard).toHaveBeenCalledTimes(6);
  });

  it("is ONE button whose NAME flips, never two and never aria-pressed", async () => {
    await mountPage();
    const control = pauseButton();
    expect(control).not.toHaveAttribute("aria-pressed");
    expect(control).not.toHaveAttribute("aria-label");
    expect(screen.queryByRole("button", { name: t("checkin.resume") })).toBeNull();

    await click(control);
    expect(screen.queryByRole("button", { name: t("checkin.pause") })).toBeNull();
    expect(resumeButton()).toBeInTheDocument();
  });

  it("carries the 44px floor, the focus ring and a TEXT label — never colour alone", async () => {
    await mountPage();
    const control = pauseButton();
    // size="md" -> min-h-11 = 44px; sm is min-h-9 = 36px and under the floor.
    // Never a measurement: jsdom has no layout engine and no Tailwind pipeline,
    // so getBoundingClientRect() is 0 and getComputedStyle().minHeight is empty.
    expect(control).toHaveClass("min-h-11");
    expect(control).toHaveClass("focus-visible:outline-focus");
    // min-h-11 is min-HEIGHT only. The x44 width half is carried by the text
    // label — which is also why there is no aria-label variant: an aria-label
    // would override the visible text and break "the name IS the label".
    expect(control).toHaveTextContent(t("checkin.pause"));

    await click(control);
    expect(resumeButton()).toHaveTextContent(t("checkin.resume"));
  });

  it("is the FIRST control in the section and precedes the rows in the DOM", async () => {
    // A 2.2.2 mechanism placed after the content it governs is reachable only by
    // walking content that repaints under the walk.
    await mountPage();
    expect(within(section()).getAllByRole("button")[0]).toBe(pauseButton());
    expect(
      pauseButton().compareDocumentPosition(rows()[0]) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
  });

  it("keeps focus on the control across the press", async () => {
    await mountPage();
    const control = pauseButton();
    control.focus();
    await click(control);
    expect(document.activeElement).toBe(resumeButton());
    expect(document.activeElement).toBe(control);
  });

  it("is present in the EMPTY state — the content auto-updates whether or not rows exist", async () => {
    getQueueBoard.mockResolvedValue({ entries: [], waiting_total: 0 });
    await mountPage();
    expect(screen.getByText(t("queueBoard.empty"))).toBeInTheDocument();
    expect(pauseButton()).toBeInTheDocument();
    expect(freshnessLine()).toBeInTheDocument();
  });

  it("is present in the ERROR state — a request is still going out under the retry button", async () => {
    // The shipped page gates its pause row on `live` and is right to: its loop
    // has a terminal, and offering a pause for a loop that can never run again
    // is a lie about the page. F59's loop has NO terminal, so in the error arm a
    // request lands every 5-60s and will replace the retry button under her
    // thumb without her acting. That is 2.2.2's subject exactly, which is why
    // the `live &&` gate does not come across.
    getQueueBoard.mockRejectedValue(new ApiError(503, "UNKNOWN", "down"));
    await mountPage();
    expect(screen.getByText(t("queueBoard.loadFailed"))).toBeInTheDocument();
    expect(pauseButton()).toBeInTheDocument();
    expect(freshnessLine()).toBeInTheDocument();
  });

  it("honours a retry pressed while paused — the ONE state where both controls render", async () => {
    // F33's page gates its pause row on `live`, so retry and pause can never be
    // on screen together there. F59 dropped that gate (the loop has no terminal)
    // and inherited a retry() that goes through tick(), which returns at once
    // while the loop is stopped: a labelled, enabled, focusable button that did
    // nothing. A manual press is not auto-updating content, so serving it does
    // not weaken the 2.2.2 pause — and the pause must SURVIVE, because cancelling
    // it silently would undo something she explicitly asked for.
    getQueueBoard.mockRejectedValue(new ApiError(503, "UNKNOWN", "down"));
    await mountPage();
    await click(pauseButton());
    const before = getQueueBoard.mock.calls.length;

    getQueueBoard.mockResolvedValue(board(2));
    await click(screen.getByRole("button", { name: t("checkin.retry") }));
    expect(getQueueBoard).toHaveBeenCalledTimes(before + 1);
    expect(rows()).toHaveLength(2);

    // Still paused: no loop rearmed, and the sentence still says so.
    expect(resumeButton()).toBeInTheDocument();
    expect(freshnessLine()).toHaveTextContent(t("checkin.pausedAt"));
    await advance(POLL * 6);
    expect(getQueueBoard).toHaveBeenCalledTimes(before + 1);
  });

  it("is absent before the first response — a pause offered then is a lie about the page", async () => {
    getQueueBoard.mockReturnValue(new Promise(() => undefined));
    renderPage();
    await flush();
    expect(screen.getByTestId("queue-board-loading-status")).toHaveTextContent(
      t("queueBoard.loading"),
    );
    expect(screen.queryByRole("button", { name: t("checkin.pause") })).toBeNull();
    expect(screen.queryByTestId("queue-board-freshness")).toBeNull();
  });
});

// --- D12, the freshness line and the two announced regions.

describe("D12 — the freshness line", () => {
  it("reads as three different SENTENCES, with paused beating stale", async () => {
    // One string plus a class would make user-paused and backed-off-stale differ
    // only by colour, which is the defect this rule exists to catch — reproduced
    // inside the rule against it.
    await mountPage();
    const live = freshnessLine().textContent ?? "";
    expect(freshnessLine()).toHaveTextContent(t("checkin.updatedAt"));
    expect(freshnessLine()).toHaveTextContent(NOW_JERUSALEM);

    await click(pauseButton());
    const paused = freshnessLine().textContent ?? "";
    expect(freshnessLine()).toHaveTextContent(t("checkin.pausedAt"));

    await click(resumeButton());
    getQueueBoard.mockRejectedValue(new Error("network"));
    await advance(POLL);
    const stale = freshnessLine().textContent ?? "";
    expect(freshnessLine()).toHaveTextContent(t("checkin.staleAt"));

    expect(new Set([live, paused, stale]).size).toBe(3);

    // A stopped loop cannot fail a tick, so the stop is the cause in force and
    // the resume control is the remedy.
    await click(pauseButton());
    expect(freshnessLine()).toHaveTextContent(t("checkin.pausedAt"));
    expect(freshnessLine()).not.toHaveTextContent(t("checkin.staleAt"));
  });

  it("states NOTHING before the first success — «עודכן» with no time is a false claim", async () => {
    // The kiosk boots while the API is down: view is `failed`, so updatedAt has
    // never been written and there is no time to state. All three sentences are
    // LEADS followed by a time in its own <bdi> (he.ts:507-509), so the lead
    // alone renders «עודכן » — the page's one honesty signal asserting an update
    // that never happened, at 59px, on a wall. The row still renders, and with
    // it the pause control, because the loop is alive and 2.2.2 still applies;
    // only the SENTENCE waits. FloorPanel.tsx:378-381 is the shipped form of the
    // same guard, in the app one directory over.
    getQueueBoard.mockRejectedValue(new ApiError(503, "UNKNOWN", "down"));
    await mountPage();
    expect(freshnessLine().textContent).toBe("");
    expect(pauseButton()).toBeInTheDocument();

    // Pausing in that arm must not invent one either.
    await click(pauseButton());
    expect(freshnessLine().textContent).toBe("");

    // And the moment a response lands, the sentence arrives with its time.
    getQueueBoard.mockResolvedValue(board(2));
    await click(resumeButton());
    expect(freshnessLine()).toHaveTextContent(t("checkin.updatedAt"));
    expect(freshnessLine()).toHaveTextContent(NOW_JERUSALEM);
  });

  it("stays OUTSIDE every announced region and is never aria-hidden", async () => {
    // aria-hidden would make the page's only honesty signal sighted-only, and a
    // role="status" rewritten every five seconds announces the page forever.
    await mountPage();
    expect(freshnessLine().closest(ANNOUNCED)).toBeNull();
    expect(freshnessLine()).not.toHaveAttribute("aria-hidden");
  });

  it("NEGATIVE CONTROL — the same selector DOES match a line inside a role=status", () => {
    // Without this the assertion above is indistinguishable from a selector that
    // matches nothing anywhere. Every live region in this repo is a bare
    // role="status" with no aria-live attribute, and closest() matches
    // attributes rather than implicit ARIA.
    render(
      <p role="status">
        <span data-testid="inside-the-region">עודכן 14:07</span>
      </p>,
    );
    expect(screen.getByTestId("inside-the-region").closest(ANNOUNCED)).not.toBeNull();
  });
});

describe("D12 — the poll never writes into the cue region", () => {
  it("leaves the CUE region untouched across three ticks that change the board", async () => {
    // Scoped BY TESTID and never to [role="status"] broadly: the loading region
    // is a SECOND role="status" that legitimately unmounts on the first settled
    // response, so a broad observer goes red against correct code and gets
    // loosened into the vacuous form.
    //
    // The region is populated first from a user-initiated press — an empty
    // region has no Text node to replace and the observation would prove
    // nothing. The board CHANGES on every tick, because assigning an identical
    // string still replaces the Text node.
    await mountPage();
    await click(pauseButton());
    await click(resumeButton());
    expect(cueRegion().textContent).not.toBe("");

    const observer = observe(cueRegion());

    getQueueBoard.mockResolvedValueOnce(board(2));
    await advance(POLL);
    getQueueBoard.mockResolvedValueOnce(board(4));
    await advance(POLL);
    getQueueBoard.mockResolvedValueOnce(board(4));
    await advance(POLL);

    // BOTH halves: the ticks happened, and the region did not move. Five calls —
    // the mount, resume's immediate fetch, and the three ticks.
    expect(getQueueBoard).toHaveBeenCalledTimes(5);
    expect(rows()).toHaveLength(4);
    expect(observer.takeRecords()).toEqual([]);
    observer.disconnect();
  });

  it("announces NO content at all, not even a called row", async () => {
    // Deliberately unlike the position page, which announces the waiting ->
    // called edge because it is HER ticket and the one thing she came for. This
    // board is about other people: «מיכל, גשי לדלפק» in a stranger's screen
    // reader is both noise and a broadcast she did not agree to.
    await mountPage();
    getQueueBoard.mockResolvedValue({
      entries: [entry(1), entry(2, { called: true })],
      waiting_total: 2,
    });
    await advance(POLL);
    expect(screen.getByText(t("queueBoard.called"))).toBeInTheDocument();
    expect(cueRegion()).not.toHaveTextContent(t("queueBoard.called"));
    expect(cueRegion().textContent).toBe("");
  });
});

// --- The rendered states.

describe("the rendered board", () => {
  it("numbers the rows from the payload and renders the names it was given", async () => {
    await mountPage();
    expect(rows()).toHaveLength(3);
    expect(rows()[0]).toHaveTextContent("1");
    expect(rows()[0]).toHaveTextContent(NAMES[0]);
    expect(rows()[2]).toHaveTextContent("3");
    expect(rows()[2]).toHaveTextContent(NAMES[2]);
  });

  it.each([1, 5, 8])("renders %i entries without the client asserting a count", async (count) => {
    // D4: the row cap is a SERVER bound. Raising BOARD_ROW_LIMIT must need no
    // frontend change at all, so nothing here may hard-code five.
    getQueueBoard.mockResolvedValue(board(count));
    await mountPage();
    expect(rows()).toHaveLength(count);
  });

  it("renders TWO rows with an identical first name, at their two positions", async () => {
    // F33's Ruling 3: one woman can hold two tickets and the board must not
    // deduplicate — the only key that would is her phone, and no read here is
    // keyed on it. This is also the test that fails if anyone keys the list by
    // name.
    getQueueBoard.mockResolvedValue({
      entries: [entry(3, { first_name: "נועה" }), entry(5, { first_name: "נועה" })],
      waiting_total: 2,
    });
    await mountPage();
    expect(rows()).toHaveLength(2);
    expect(rows()[0]).toHaveTextContent("3");
    expect(rows()[1]).toHaveTextContent("5");
    expect(screen.getAllByText("נועה")).toHaveLength(2);
  });

  it("renders the empty state as a designed state, never a blank page", async () => {
    getQueueBoard.mockResolvedValue({ entries: [], waiting_total: 0 });
    await mountPage();
    expect(screen.getByText(t("queueBoard.empty"))).toBeInTheDocument();
    expect(screen.getByText(t("queueBoard.emptyHint"))).toBeInTheDocument();
    expect(rows()).toHaveLength(0);
    expect(screen.queryByTestId("queue-board-overflow")).toBeNull();
  });

  it("COMPUTES the overflow count rather than echoing the total", async () => {
    // An off-by-one here is a wrong number on a wall, and «ועוד 40 בתור» beside
    // five rows is the number the room would act on.
    getQueueBoard.mockResolvedValue(board(5, { waiting_total: 40 }));
    await mountPage();
    const overflow = screen.getByTestId("queue-board-overflow");
    expect(overflow).toHaveTextContent("35");
    expect(overflow).not.toHaveTextContent("40");
    expect(overflow).toHaveTextContent(t("queueBoard.overflow", { count: 35 }));
  });

  it("renders no overflow line when the board is not truncated", async () => {
    getQueueBoard.mockResolvedValue(board(3, { waiting_total: 3 }));
    await mountPage();
    expect(screen.queryByTestId("queue-board-overflow")).toBeNull();
  });

  it("renders a called row as a WORD, with the number and the name still text-ink", async () => {
    // ⚠ SEEDED THROUGH THE STUBBED CLIENT, which is the only way it can be
    // produced: nothing in the product writes called_at until F58, so there is
    // no product path to drive this through and no e2e journey may try.
    //
    // WCAG 1.4.1: the word is what keeps the highlight out of colour-alone. At
    // four metres on a cheap panel a tint is the first thing a compressed
    // backlight loses, and a woman with a colour-vision difference is the entire
    // audience.
    getQueueBoard.mockResolvedValue({
      entries: [entry(1), entry(2, { first_name: "מיכל", called: true })],
      waiting_total: 2,
    });
    await mountPage();

    const word = screen.getByText(t("queueBoard.called"));
    expect(word).toHaveClass("text-warning-text");
    const calledRow = rows()[1];
    expect(calledRow).toContainElement(word);
    expect(calledRow).toHaveClass("border-s-8");
    expect(calledRow).toHaveClass("border-gold-strong");
    // The biggest glyphs on the screen are what she is scanning for; dropping
    // them to signal a state three other things already carry is the wrong trade.
    expect(within(calledRow).getByText("2")).toHaveClass("text-ink");
    expect(within(calledRow).getByText("מיכל")).toHaveClass("text-ink");
    // An uncalled row carries none of it.
    expect(rows()[0]).not.toHaveClass("border-s-8");
  });

  it("gives the loading skeleton a DEFINITE height, so the band is not a blank screen", async () => {
    // `variant="block"` is `h-full w-full`, and h-full against an auto-height
    // containing block resolves to 0 — the wrapper's own `flex-1` distributes
    // nothing inside a content-sized column flex container, so the shipped
    // skeleton measured 0px tall at 1920x1080 and at 375x667. The television
    // showed the heading, the gold rule and nothing else: the exact "broken or
    // empty" ambiguity W-load/F-10 designed the band to remove. `min-h-` does
    // not fix it either — min-height leaves the containing block indefinite, so
    // the bar stays 0 inside a reserved box. jsdom has no layout engine, so the
    // class is the only guard available.
    getQueueBoard.mockReturnValue(new Promise(() => undefined));
    const { container } = renderPage();
    await flush();
    const shimmer = container.querySelector(".animate-skeleton");
    expect(shimmer).not.toBeNull();
    expect(shimmer?.parentElement).toHaveClass("h-[567px]");
  });

  it("renders the recoverable failure with a retry, and the retry heals the board", async () => {
    getQueueBoard.mockRejectedValue(new ApiError(503, "UNKNOWN", "down"));
    await mountPage();
    expect(screen.getByText(t("queueBoard.loadFailed"))).toBeInTheDocument();

    getQueueBoard.mockResolvedValue(board(2));
    await click(screen.getByRole("button", { name: t("checkin.retry") }));
    expect(rows()).toHaveLength(2);
    expect(screen.queryByText(t("queueBoard.loadFailed"))).toBeNull();
  });
});

// --- A34 / SC 1.4.4 — the second criterion axe cannot see. Class assertions,
// --- never measurements: jsdom has no layout engine and axe has never measured
// --- a font size or a viewing distance.

describe("A34 — the type scale", () => {
  it("puts a rem term inside EVERY clamp() the page renders", async () => {
    // A vh-only preferred value makes the A11yMenu's text-size boost a complete
    // no-op at 1080p, at 4K and on a phone — and browser zoom does not rescue
    // it, because page zoom shrinks the CSS-pixel viewport and enlarges the
    // pixel, so vh text is net-constant by construction. That is SC 1.4.4
    // failing green in CI.
    getQueueBoard.mockResolvedValue(board(5, { waiting_total: 40 }));
    const { container } = await mountPage();

    const preferred = [...container.querySelectorAll<HTMLElement>("[class]")]
      .flatMap((node) => [...node.className.matchAll(/clamp\(([^)]+)\)/g)])
      .map((match) => match[1].split(",")[1]);

    expect(preferred.length).toBeGreaterThan(4);
    for (const term of preferred) {
      expect(term, `${term} has no rem term — the text-size boost is inert`).toContain("rem");
    }
  });

  it("keeps the freshness and overflow lines at the NAME scale, not the small bucket", async () => {
    // Two of the spec's own arguments rest on these being readable from a seat.
    // The freshness line is what resolves the whole 2.2.2 wall-screen tension —
    // a paused or stale board that reads as live to the room is the exact
    // failure it is invoked to prevent. The overflow line is the only sentence
    // telling a woman the queue is longer than the screen.
    getQueueBoard.mockResolvedValue(board(5, { waiting_total: 40 }));
    await mountPage();
    expect(freshnessLine()).toHaveClass(NAME_SCALE);
    expect(screen.getByTestId("queue-board-overflow")).toHaveClass(NAME_SCALE);
  });

  it("keeps the pause label at the SMALL scale — W-5, and A34 must not promote it", async () => {
    await mountPage();
    // The clamp is on a DESCENDANT and never on the Button: sizes.md bakes
    // text-base into the component and cn() is a plain join with no
    // tailwind-merge, so a className on the Button ships BOTH utilities and
    // Tailwind's stylesheet order decides the rendered size.
    const label = within(pauseButton()).getByText(t("checkin.pause"));
    expect(label).toHaveClass(SMALL_SCALE);
    expect(pauseButton()).not.toHaveClass(SMALL_SCALE);
  });

  it("keeps the heading, the position number and the name at their own scales", async () => {
    await mountPage();
    expect(screen.getByRole("heading", { level: 1 })).toHaveClass(HEADING_SCALE);
    expect(within(rows()[0]).getByText("1")).toHaveClass(POSITION_SCALE);
    expect(within(rows()[0]).getByText(NAMES[0])).toHaveClass(NAME_SCALE);
  });

  it("lets a long name wrap instead of scrolling the document sideways", async () => {
    // At 375px with a 32px root the row is a 106.8px number beside an 84.3px
    // name in a 311px box, and a 12-character Hebrew name is roughly 500px of
    // content. The same two fixes the shipped suite already applied to the
    // gallery strip and the footer handle to keep TEXT_RESIZE_BROKEN_AT_375
    // empty.
    await mountPage();
    const name = within(rows()[0]).getByText(NAMES[0]);
    expect(name).toHaveClass("min-w-0");
    expect(name).toHaveClass("[overflow-wrap:anywhere]");
    expect(rows()[0]).toHaveClass("flex-wrap");
  });
});

describe("A16 — the page owns neither the title nor the mount focus", () => {
  it("does not touch document.title and does not move focus on mount", async () => {
    // SENTINEL form, rendered IN ISOLATION. router.tsx does title, scrollTo and
    // focus in one parent effect, and React flushes a child's passive effects
    // BEFORE its parent's — so a page-level write here is dead code that reads
    // as working when asserted through <Router />, which is why this is not
    // rendered through it.
    document.title = "SENTINEL";
    const before = document.activeElement;
    await mountPage();
    expect(document.title).toBe("SENTINEL");
    expect(document.activeElement).toBe(before);
  });
});

describe("axe", () => {
  // EXPLICITLY NOT SUFFICIENT. Axe has no SC 2.2.2 rule and measures no font
  // size, so the pause block and the type-scale block above are the only
  // automated coverage of two legally required criteria on this screen. Neither
  // may be deleted as redundant with these three.
  it("passes with zero violations on the live board", async () => {
    vi.useRealTimers();
    getQueueBoard.mockResolvedValue(board(5, { waiting_total: 40 }));
    const { container } = renderPage();
    await screen.findByTestId("queue-board-freshness");
    const results = await run(container);
    expect(results.violations.map((violation) => violation.id)).toEqual([]);
  });

  it("passes with zero violations on the empty board", async () => {
    vi.useRealTimers();
    getQueueBoard.mockResolvedValue({ entries: [], waiting_total: 0 });
    const { container } = renderPage();
    await screen.findByText(t("queueBoard.empty"));
    const results = await run(container);
    expect(results.violations.map((violation) => violation.id)).toEqual([]);
  });

  it("passes with zero violations on the error arm", async () => {
    vi.useRealTimers();
    getQueueBoard.mockRejectedValue(new ApiError(503, "UNKNOWN", "down"));
    const { container } = renderPage();
    await screen.findByText(t("queueBoard.loadFailed"));
    const results = await run(container);
    expect(results.violations.map((violation) => violation.id)).toEqual([]);
  });
});
