import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { run } from "axe-core";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { BoutiqueResponse, TicketView } from "../api";
import { StorefrontLayout } from "../components/StorefrontLayout";
import i18n from "../i18n";
import { readCheckinTicket, writeCheckinTicket } from "../lib/checkinTicket";
import { QueuePositionPage } from "../routes/QueuePositionPage";
import { PRIVACY_FIXTURE } from "../test/boutique";

// Spread the real module so ApiError keeps its real implementation: every
// terminal decision on this page is made from an error's status and code, and a
// stubbed error class would make the whole terminal suite vacuous.
vi.mock("../api", async () => {
  const actual = await vi.importActual<typeof import("../api")>("../api");
  return {
    ...actual,
    api: { ...actual.api, getQueuePosition: vi.fn() },
    getBoutiqueOnce: vi.fn(),
  };
});

const { ApiError, api, getBoutiqueOnce } = await import("../api");
const getQueuePosition = vi.mocked(api.getQueuePosition);
const loadBoutique = vi.mocked(getBoutiqueOnce);

const TICKET_ID = "11111111-2222-3333-4444-555555555555";
const POLL = 5_000;

// 11:07Z is 14:07 in Jerusalem (IDT, UTC+3) and 07:07 in New York — and
// package.json pins TZ=America/New_York for the test run, so an unzoned read
// prints 07:07 and the freshness assertion fails loudly rather than quietly.
const NOW = "2026-08-04T11:07:00Z";
const NOW_JERUSALEM = "14:07";

// Every live region in this repo is a bare role="status" with no aria-live
// attribute, and closest() matches ATTRIBUTES rather than implicit ARIA — so
// the earlier `closest('[aria-live]')` form matched nothing anywhere and could
// not fail. All three selectors, and a negative control below proves it bites.
const ANNOUNCED = '[role="status"],[role="alert"],[aria-live]';

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
    ...PRIVACY_FIXTURE,
  };
}

function ticket(overrides: Partial<TicketView> = {}): TicketView {
  return { id: TICKET_ID, status: "waiting", position: 3, called_at: null, ...overrides };
}

function t(key: string): string {
  return i18n.t(key);
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

function renderPage(ticketId = TICKET_ID) {
  return render(
    <StorefrontLayout>
      <QueuePositionPage ticketId={ticketId} />
    </StorefrontLayout>,
  );
}

async function mountPage(ticketId = TICKET_ID) {
  const view = renderPage(ticketId);
  await flush();
  return view;
}

function section(): HTMLElement {
  return screen.getByTestId("queue-position");
}

function freshnessLine(): HTMLElement {
  return screen.getByTestId("queue-freshness");
}

function cueRegion(): HTMLElement {
  return screen.getByTestId("queue-cue");
}

function positionNumber(): HTMLElement {
  return screen.getByTestId("queue-number");
}

function pauseButton(): HTMLElement {
  return screen.getByRole("button", { name: t("checkin.pause") });
}

function resumeButton(): HTMLElement {
  return screen.getByRole("button", { name: t("checkin.resume") });
}

beforeEach(() => {
  vi.clearAllMocks();
  window.sessionStorage.clear();
  window.history.replaceState(null, "", `/q/${TICKET_ID}`);
  document.title = "";
  loadBoutique.mockResolvedValue(boutique());
  getQueuePosition.mockResolvedValue(ticket());
  vi.useFakeTimers();
  vi.setSystemTime(new Date(NOW));
  setHidden(false);
});

afterEach(() => {
  vi.useRealTimers();
  setHidden(false);
});

// --- D9, the poll mechanisms this page COPIES from the board. Each has its own
// --- named assertion and none of them is covered by any of the others.

describe("D9(1) — schedule-after-settle, never setInterval", () => {
  it("issues exactly one request per tick and never two in flight", async () => {
    // The next tick is armed from the PREVIOUS request's .finally(), so at most
    // one poll is in flight per tab BY CONSTRUCTION — there is nothing to abort
    // and no in-flight flag to get wrong.
    getQueuePosition.mockReturnValue(new Promise(() => undefined));
    renderPage();
    await flush();
    expect(getQueuePosition).toHaveBeenCalledTimes(1);

    await advance(POLL * 4);
    expect(getQueuePosition).toHaveBeenCalledTimes(1);
  });

  it("beats once per interval once the request settles", async () => {
    await mountPage();
    expect(getQueuePosition).toHaveBeenCalledTimes(1);
    await advance(POLL);
    expect(getQueuePosition).toHaveBeenCalledTimes(2);
    await advance(POLL);
    expect(getQueuePosition).toHaveBeenCalledTimes(3);
  });
});

describe("D9(a) — the unmount guard, which is the fix 0c7015a shipped", () => {
  it("arms nothing after unmount, even when a request was in flight", async () => {
    // clearTick() ALONE cancels only the timer armed right now. The arming site
    // is a .finally(), which runs AFTER the cleanup when a request is in flight,
    // and nothing in tick -> load -> finally -> schedule touches React state —
    // so an orphaned loop cannot be broken by unmounting. On this surface the
    // orphan is an anonymous 5s loop against a public endpoint, from a phone in
    // a bag, for the rest of the session.
    const pending = deferred<TicketView>();
    getQueuePosition.mockReturnValue(pending.promise);
    const view = renderPage();
    await flush();
    expect(getQueuePosition).toHaveBeenCalledTimes(1);

    view.unmount();
    await act(async () => {
      pending.resolve(ticket());
      await vi.advanceTimersByTimeAsync(0);
    });

    await advance(POLL * 10);
    expect(getQueuePosition).toHaveBeenCalledTimes(1);
  });
});

describe("D9(4) — document.hidden", () => {
  it("stops polling while the tab is hidden and fetches at once when it comes back", async () => {
    // Browsers already throttle background timers to >=1/minute, so an unpaused
    // loop looks live while being a minute stale. And waiting out a full
    // interval on return adds five more seconds of a wrong screen at the worst
    // possible moment.
    await mountPage();
    expect(getQueuePosition).toHaveBeenCalledTimes(1);

    await fireVisibility(true);
    await advance(POLL * 4);
    expect(getQueuePosition).toHaveBeenCalledTimes(1);

    await fireVisibility(false);
    expect(getQueuePosition).toHaveBeenCalledTimes(2);
  });
});

describe("D9(5) — the backoff ladder and its cap, in both directions", () => {
  it("doubles 5s -> 60s, never past the cap, and the next call still comes", async () => {
    getQueuePosition.mockRejectedValue(new Error("network"));
    await mountPage();
    expect(getQueuePosition).toHaveBeenCalledTimes(1);

    // 5 -> 10 -> 20 -> 40 -> 80 clamped to 60.
    for (const [index, gap] of [10_000, 20_000, 40_000, 60_000].entries()) {
      // One millisecond short of the gap: nothing yet.
      await advance(gap - 1);
      expect(getQueuePosition).toHaveBeenCalledTimes(index + 1);
      await advance(1);
      expect(getQueuePosition).toHaveBeenCalledTimes(index + 2);
    }

    // The cap holds rather than doubling to 120s — the next call still comes,
    // at 60s and not later.
    await advance(60_000);
    expect(getQueuePosition).toHaveBeenCalledTimes(6);

    // And one success resets the ladder to the base interval.
    getQueuePosition.mockResolvedValue(ticket());
    await advance(60_000);
    expect(getQueuePosition).toHaveBeenCalledTimes(7);
    await advance(POLL);
    expect(getQueuePosition).toHaveBeenCalledTimes(8);
  });
});

// --- D11, SC 2.2.2 (Level A) — a LEGAL bar here, and axe has NO rule for it.
// --- These assertions are the ONLY automated coverage of the criterion and must
// --- not be dropped as redundant with the axe row at the bottom of this file.

describe("D11 — the user-operable pause", () => {
  it("stops the loop when pressed, and resuming fetches before the interval elapses", async () => {
    await mountPage();
    expect(getQueuePosition).toHaveBeenCalledTimes(1);

    await click(pauseButton());
    await advance(POLL * 6);
    expect(getQueuePosition).toHaveBeenCalledTimes(1);

    await click(resumeButton());
    // Immediately, not one interval later: a resume is a fresh user intent.
    expect(getQueuePosition).toHaveBeenCalledTimes(2);
  });

  it("resets a backed-off gap, so the control does not look like it failed", async () => {
    // One success first — the control only exists once there is auto-updating
    // content for it to govern.
    await mountPage();
    getQueuePosition.mockRejectedValue(new Error("network"));
    await advance(POLL);
    await advance(10_000);
    await advance(20_000);
    expect(getQueuePosition).toHaveBeenCalledTimes(4);

    getQueuePosition.mockResolvedValue(ticket());
    await click(pauseButton());
    await click(resumeButton());
    expect(getQueuePosition).toHaveBeenCalledTimes(5);

    // Back at the base interval rather than inheriting the 80s gap.
    await advance(POLL);
    expect(getQueuePosition).toHaveBeenCalledTimes(6);
  });

  it("is ONE button whose name changes, never two and never aria-pressed", async () => {
    await mountPage();
    const control = pauseButton();
    expect(control).not.toHaveAttribute("aria-pressed");
    expect(screen.queryByRole("button", { name: t("checkin.resume") })).toBeNull();

    await click(control);
    expect(screen.queryByRole("button", { name: t("checkin.pause") })).toBeNull();
    expect(resumeButton()).toBeInTheDocument();
  });

  it("carries the 44px floor, the focus ring and a text label — never colour alone", async () => {
    await mountPage();
    const control = pauseButton();
    // size="md" -> min-h-11 = 44px. sm is min-h-9 = 36px, under the floor. Never
    // a measurement: jsdom has no layout engine and no Tailwind pipeline, so
    // getBoundingClientRect() is 0 and getComputedStyle().minHeight is empty.
    expect(control).toHaveClass("min-h-11");
    expect(control).toHaveClass("focus-visible:outline-focus");
    // min-h-11 is min-HEIGHT only. The x44 width half is carried by the text
    // label, which is also why there is no aria-label variant: an aria-label
    // would override the visible text and break "the name IS the label".
    expect(control).toHaveTextContent(t("checkin.pause"));

    await click(control);
    expect(resumeButton()).toHaveTextContent(t("checkin.resume"));
  });

  it("is the FIRST control in the section, and sits before the auto-updating number", async () => {
    // A 2.2.2 mechanism placed after the content it governs is reachable only by
    // walking content that repaints under the walk.
    await mountPage();
    expect(within(section()).getAllByRole("button")[0]).toBe(pauseButton());
    expect(
      pauseButton().compareDocumentPosition(positionNumber()) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
  });

  it("keeps focus on the control across the press, so the rename does not drop her to body", async () => {
    await mountPage();
    const control = pauseButton();
    control.focus();
    await click(control);
    expect(document.activeElement).toBe(resumeButton());
    expect(document.activeElement).toBe(control);
  });
});

describe("D12 — the freshness line reads as three different SENTENCES", () => {
  it("says live, paused and stale in words rather than in a class", async () => {
    await mountPage();
    const live = freshnessLine().textContent ?? "";
    expect(freshnessLine()).toHaveTextContent(t("checkin.updatedAt"));
    expect(freshnessLine()).toHaveTextContent(NOW_JERUSALEM);

    await click(pauseButton());
    const paused = freshnessLine().textContent ?? "";
    expect(freshnessLine()).toHaveTextContent(t("checkin.pausedAt"));

    await click(resumeButton());
    getQueuePosition.mockRejectedValue(new Error("network"));
    await advance(POLL);
    const stale = freshnessLine().textContent ?? "";
    expect(freshnessLine()).toHaveTextContent(t("checkin.staleAt"));

    expect(new Set([live, paused, stale]).size).toBe(3);
  });

  it("keeps the last good position on screen and labels it stale rather than blanking", async () => {
    await mountPage();
    expect(positionNumber()).toHaveTextContent("3");

    getQueuePosition.mockRejectedValue(new ApiError(503, "UNKNOWN", "down"));
    await advance(POLL);
    expect(positionNumber()).toHaveTextContent("3");
    expect(freshnessLine()).toHaveTextContent(t("checkin.staleAt"));
  });
});

describe("D12 — the poll never writes into the announced region", () => {
  it("leaves the region untouched across three ticks that change the position", async () => {
    // The naive version passes against the broken code: assigning an identical
    // string still replaces the Text node, so a single tick observing an
    // unchanged value proves nothing. The position CHANGES on every tick here.
    await mountPage();
    // Populate the region first, from a user-initiated event — an empty region
    // has no Text node to replace and the observation would be vacuous.
    await click(pauseButton());
    await click(resumeButton());
    expect(cueRegion().textContent).not.toBe("");

    const observer = new MutationObserver(() => undefined);
    observer.observe(cueRegion(), {
      subtree: true,
      childList: true,
      characterData: true,
      attributes: true,
    });

    getQueuePosition.mockResolvedValueOnce(ticket({ position: 2 }));
    await advance(POLL);
    getQueuePosition.mockResolvedValueOnce(ticket({ position: 1 }));
    await advance(POLL);
    getQueuePosition.mockResolvedValueOnce(ticket({ position: 1 }));
    await advance(POLL);

    // BOTH halves: the ticks happened, and the region did not move. Five calls:
    // the mount, resume's immediate fetch, and the three ticks.
    expect(getQueuePosition).toHaveBeenCalledTimes(5);
    expect(positionNumber()).toHaveTextContent("1");
    expect(observer.takeRecords()).toEqual([]);
    observer.disconnect();
  });

  it("announces the called transition ONCE, on the edge and never on a later tick", async () => {
    await mountPage();
    expect(cueRegion()).not.toHaveTextContent(t("checkin.called"));

    getQueuePosition.mockResolvedValue(
      ticket({ position: null, called_at: "2026-08-04T11:08:00Z" }),
    );
    await advance(POLL);
    expect(cueRegion()).toHaveTextContent(t("checkin.called"));

    const observer = new MutationObserver(() => undefined);
    observer.observe(cueRegion(), {
      subtree: true,
      childList: true,
      characterData: true,
      attributes: true,
    });
    await advance(POLL);
    await advance(POLL);
    expect(getQueuePosition).toHaveBeenCalledTimes(4);
    expect(observer.takeRecords()).toEqual([]);
    observer.disconnect();
  });

  it("keeps the freshness line OUTSIDE every announced region", async () => {
    // aria-hidden would make the page's only honesty signal sighted-only, so the
    // line is visible and reachable — it just must never be announced.
    await mountPage();
    expect(freshnessLine().closest(ANNOUNCED)).toBeNull();
    expect(freshnessLine()).not.toHaveAttribute("aria-hidden");
  });

  it("NEGATIVE CONTROL — the same selector DOES match a line inside a role=status", () => {
    // Without this the assertion above is indistinguishable from a selector that
    // matches nothing anywhere, which is what the earlier draft shipped.
    render(
      <p role="status">
        <span data-testid="inside-the-region">עודכן 14:07</span>
      </p>,
    );
    expect(screen.getByTestId("inside-the-region").closest(ANNOUNCED)).not.toBeNull();
  });
});

// --- D10, F33's terminal set. NOT F34's {401, 403}: the storefront carries no
// --- session, so both of those are unreachable here.

describe("D10 — the terminals stop the loop", () => {
  it("stops on a 404 and renders the not-found state", async () => {
    getQueuePosition.mockRejectedValue(new ApiError(404, "NOT_FOUND", "Resource not found."));
    await mountPage();

    expect(screen.getByText(t("checkin.notFound"))).toBeInTheDocument();
    await advance(POLL * 10);
    expect(getQueuePosition).toHaveBeenCalledTimes(1);
  });

  it("stops on a malformed id, which cannot become well-formed", async () => {
    getQueuePosition.mockRejectedValue(
      new ApiError(400, "VALIDATION_ERROR", "Input failed validation."),
    );
    await mountPage("not-a-uuid");

    expect(screen.getByText(t("checkin.notFound"))).toBeInTheDocument();
    await advance(POLL * 10);
    expect(getQueuePosition).toHaveBeenCalledTimes(1);
  });

  it("stops on a 200 whose status is done — the only place a success ends a loop", async () => {
    // The `done` fixture is SEEDED here, and it is the only way it can be
    // produced: nothing in F33 writes a terminal status, so there is no product
    // path to drive this through. Getting this wrong is invisible — the page
    // keeps working, it just never stops.
    await mountPage();
    expect(getQueuePosition).toHaveBeenCalledTimes(1);

    getQueuePosition.mockResolvedValue(ticket({ status: "done", position: null }));
    await advance(POLL);
    expect(screen.getByText(t("checkin.closed"))).toBeInTheDocument();

    await advance(POLL * 10);
    expect(getQueuePosition).toHaveBeenCalledTimes(2);
  });

  it("stops on a 200 whose status is removed", async () => {
    await mountPage();
    getQueuePosition.mockResolvedValue(ticket({ status: "removed", position: null }));
    await advance(POLL);
    expect(screen.getByText(t("checkin.closed"))).toBeInTheDocument();

    await advance(POLL * 10);
    expect(getQueuePosition).toHaveBeenCalledTimes(2);
  });

  it("does NOT stop on a 429 — every budget here is a fixed window, so it backs off and resumes", async () => {
    // Including the miss brake's, which is the one place a terminal 404 is
    // briefly deferred: a client that stopped on the 429 would never see it.
    await mountPage();
    getQueuePosition.mockRejectedValue(
      new ApiError(429, "TOO_MANY_ATTEMPTS", "Too many attempts. Try again later."),
    );
    await advance(POLL);
    expect(getQueuePosition).toHaveBeenCalledTimes(2);

    getQueuePosition.mockResolvedValue(ticket({ position: 2 }));
    await advance(10_000);
    expect(getQueuePosition).toHaveBeenCalledTimes(3);
    expect(positionNumber()).toHaveTextContent("2");
  });
});

describe("D8/D10 — every terminal clears the courtesy pointer", () => {
  it("clears it after a 404, so /checkin stops offering a link into a dead page", async () => {
    writeCheckinTicket(TICKET_ID);
    getQueuePosition.mockRejectedValue(new ApiError(404, "NOT_FOUND", "Resource not found."));
    await mountPage();
    expect(readCheckinTicket()).toBeNull();
  });

  it("clears it after a malformed id", async () => {
    writeCheckinTicket(TICKET_ID);
    getQueuePosition.mockRejectedValue(
      new ApiError(400, "VALIDATION_ERROR", "Input failed validation."),
    );
    await mountPage("not-a-uuid");
    expect(readCheckinTicket()).toBeNull();
  });

  it("clears it after a done status", async () => {
    writeCheckinTicket(TICKET_ID);
    await mountPage();
    expect(readCheckinTicket()).toBe(TICKET_ID);

    getQueuePosition.mockResolvedValue(ticket({ status: "done", position: null }));
    await advance(POLL);
    expect(readCheckinTicket()).toBeNull();
  });

  it("keeps it while the ticket is still live", async () => {
    writeCheckinTicket(TICKET_ID);
    await mountPage();
    await advance(POLL * 3);
    expect(readCheckinTicket()).toBe(TICKET_ID);
  });
});

describe("C15 — the page owns neither the title nor the mount focus", () => {
  it("does not touch document.title and does not move focus on mount", async () => {
    // SENTINEL form. router.tsx overwrites both one tick later — React flushes a
    // child's passive effects before its parent's — so a page-level write here
    // is dead code that reads as working when asserted through <Router />.
    document.title = "SENTINEL";
    const before = document.activeElement;
    await mountPage();
    expect(document.title).toBe("SENTINEL");
    expect(document.activeElement).toBe(before);
  });
});

describe("the rendered states", () => {
  it("shows the position as a number with the waiting sentence beside it", async () => {
    await mountPage();
    expect(positionNumber()).toHaveTextContent("3");
    expect(section()).toHaveTextContent(t("checkin.statusWaiting"));
  });

  it("replaces the number with go-to-the-counter once she has been called", async () => {
    getQueuePosition.mockResolvedValue(
      ticket({ position: null, called_at: "2026-08-04T11:08:00Z" }),
    );
    await mountPage();
    expect(screen.getByTestId("queue-called")).toHaveTextContent(t("checkin.called"));
    expect(screen.queryByTestId("queue-number")).toBeNull();
  });

  it("offers a way back to /checkin from both dead ends", async () => {
    getQueuePosition.mockRejectedValue(new ApiError(404, "NOT_FOUND", "Resource not found."));
    await mountPage();
    expect(screen.getByRole("link", { name: t("checkin.backToCheckin") })).toHaveAttribute(
      "href",
      "/checkin",
    );
  });

  it("renders the recoverable failure with a retry when nothing has loaded yet", async () => {
    getQueuePosition.mockRejectedValue(new ApiError(503, "UNKNOWN", "down"));
    await mountPage();
    expect(screen.getByText(t("checkin.loadFailed"))).toBeInTheDocument();

    getQueuePosition.mockResolvedValue(ticket({ position: 4 }));
    await click(screen.getByRole("button", { name: t("checkin.retry") }));
    expect(positionNumber()).toHaveTextContent("4");
  });

  it("shows no pause control once the loop has reached a terminal", async () => {
    // A mechanism offered for a loop that can never run again is a lie about
    // the state of the page.
    await mountPage();
    expect(pauseButton()).toBeInTheDocument();

    getQueuePosition.mockResolvedValue(ticket({ status: "done", position: null }));
    await advance(POLL);
    expect(screen.queryByRole("button", { name: t("checkin.pause") })).toBeNull();
    expect(screen.queryByRole("button", { name: t("checkin.resume") })).toBeNull();
  });
});

describe("axe", () => {
  // EXPLICITLY NOT SUFFICIENT: axe has no SC 2.2.2 rule, so the D11 block above
  // is the only automated coverage of the pause mechanism and must not be
  // deleted as redundant with these two.
  it("passes with zero violations on the live position", async () => {
    vi.useRealTimers();
    const { container } = renderPage();
    await screen.findByTestId("queue-number");
    const results = await run(container);
    expect(results.violations.map((violation) => violation.id)).toEqual([]);
  });

  it("passes with zero violations on the not-found state", async () => {
    vi.useRealTimers();
    getQueuePosition.mockRejectedValue(new ApiError(404, "NOT_FOUND", "Resource not found."));
    const { container } = renderPage();
    await screen.findByText(t("checkin.notFound"));
    const results = await run(container);
    expect(results.violations.map((violation) => violation.id)).toEqual([]);
  });
});

// --- F58 / D14: the four arms, and the precedence F58 makes reachable --------

describe("A28 — the render arms, now that in_service and called CO-OCCUR", () => {
  // ⚠ EVERY FIXTURE HERE IS SEEDED THROUGH THE STUBBED API CLIENT, and that is
  // the only way any of them can be produced: nothing the customer can do
  // writes `in_service`, `done` or `removed`. F58's five verbs are the first
  // writers in the product, which is why three of these four arms have been
  // unreachable since F33 shipped and why the ordering defect below could not
  // be seen. No backend or e2e assertion may try to drive them.

  it("«התור שלך התחיל» wins over «אפשר לגשת לדלפק» once she is IN a room", async () => {
    // THE CASE F58 CREATES. Take-next and push-assign both set status to
    // in_service and DELIBERATELY leave `called_at` standing — it is the record
    // that she was summoned and the one column the wall board reads — so the two
    // facts co-occur for the first time in the product. Under the shipped order
    // the `called` arm wins and the page tells a woman standing in a fitting
    // room to approach the counter, while «התור שלך התחיל» is unreachable on the
    // only path that produces it.
    //
    // MUTATION: restore the shipped guards and this reddens — and nothing else
    // in this file does.
    getQueuePosition.mockResolvedValue(
      ticket({ status: "in_service", position: null, called_at: "2026-08-04T11:08:00Z" }),
    );
    await mountPage();

    expect(section()).toHaveTextContent(t("checkin.statusInService"));
    expect(screen.queryByTestId("queue-called")).toBeNull();
    expect(screen.queryByTestId("queue-number")).toBeNull();
  });

  it("…and reads the same when she was taken WITHOUT being called first", async () => {
    // The arm is keyed on the STATUS, not on the absence of a position: a walk-in
    // dispatched straight off the queue was never summoned.
    getQueuePosition.mockResolvedValue(
      ticket({ status: "in_service", position: null, called_at: null }),
    );
    await mountPage();

    expect(section()).toHaveTextContent(t("checkin.statusInService"));
  });

  it("keeps «אפשר לגשת לדלפק» for a woman who was called and is STILL waiting", async () => {
    // The other half of the mutation. A call writes `called_at` and leaves the
    // status alone, so this is the state F33's own cue was written for and it
    // must not move.
    getQueuePosition.mockResolvedValue(
      ticket({ status: "waiting", position: 1, called_at: "2026-08-04T11:08:00Z" }),
    );
    await mountPage();

    expect(screen.getByTestId("queue-called")).toHaveTextContent(t("checkin.called"));
    expect(section()).not.toHaveTextContent(t("checkin.statusInService"));
    expect(screen.queryByTestId("queue-number")).toBeNull();
  });

  it("lets a CLOSED visit beat both, even carrying a call and a room", async () => {
    // F33's third deployment-gate consequence: until F58 nothing wrote `done`,
    // so the terminal arm has been unreachable in the product since the page
    // shipped. A finish closes the ticket in the same transaction that frees the
    // room, and `called_at` survives that too.
    getQueuePosition.mockResolvedValue(
      ticket({ status: "done", position: null, called_at: "2026-08-04T11:08:00Z" }),
    );
    await mountPage();

    expect(screen.getByText(t("checkin.closed"))).toBeInTheDocument();
    expect(screen.queryByTestId("queue-called")).toBeNull();
    expect(section()).not.toHaveTextContent(t("checkin.statusInService"));
  });
});
