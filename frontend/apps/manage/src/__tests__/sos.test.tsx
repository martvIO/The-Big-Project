import { StrictMode } from "react";
import { act, render } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api, ApiError } from "../api";
import type { SosAlert } from "../api";
import { IDLE_STOP_MS } from "../lib/usePoll";
import { SosProvider } from "../lib/sos";
import { useSos } from "../lib/sos-context";
import type { RaiseOutcome, SosContextValue } from "../lib/sos-context";

/**
 * The console's THIRD poll loop, and the first one that runs on every section.
 *
 * ⚠ Two of its properties are the ones a silent failure hides behind, so both
 * are pinned by name here rather than left to the overlay's tests:
 *
 *   - the gap is derived from the RESPONSE and never from React state, so the
 *     tick that first observes an alert re-arms at 2 000 ms and not at 5 000;
 *   - the loop NEVER idle-stops, because a phone in an apron pocket untouched
 *     for eleven minutes would otherwise stop receiving pages and say nothing.
 */

const NOW = "2026-08-04T08:20:00Z";
const ALERT_ID = "88888888-9999-aaaa-bbbb-cccccccccccc";

function alertRow(overrides: Partial<SosAlert> = {}): SosAlert {
  return {
    id: ALERT_ID,
    status: "open",
    raised_by: "11111111-1111-1111-1111-111111111111",
    raised_by_name: "דנה כהן",
    target_staff_user_id: null,
    target_name: null,
    room_label: "חדר 2",
    note: "צריך סיכות",
    accepted_by: null,
    accepted_by_name: null,
    acknowledged_at: null,
    created_at: NOW,
    escalated: false,
    stalled: false,
    for_me: true,
    ...overrides,
  };
}

let sos: SosContextValue;

function Consumer() {
  sos = useSos();
  return <div data-testid="count">{sos.alerts.length}</div>;
}

async function flush() {
  await act(async () => {
    await Promise.resolve();
  });
}

async function advance(ms: number) {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });
}

async function mount(options: { onSessionEnded?: () => void; strict?: boolean } = {}) {
  const tree = (
    <SosProvider onSessionEnded={options.onSessionEnded}>
      <Consumer />
    </SosProvider>
  );
  const view = render(options.strict === true ? <StrictMode>{tree}</StrictMode> : tree);
  await flush();
  return view;
}

// `unread_notifications` is OPTIONAL here and defaults to 0 — F35's count rides
// this payload, and every shipped assertion in this file is about a staffer with
// nothing waiting. Spelling it at each of the ~20 call sites would have been
// twenty chances to typo the field that carries a bell.
function stubRead(
  ...pages: { alerts: SosAlert[]; server_now: string; unread_notifications?: number }[]
) {
  const read = vi.spyOn(api, "getSos");
  const full = pages.map((page) => ({ unread_notifications: 0, ...page }));
  for (const page of full.slice(0, -1)) {
    read.mockResolvedValueOnce(page);
  }
  const last = full[full.length - 1];
  if (last !== undefined) {
    read.mockResolvedValue(last);
  }
  return read;
}

beforeEach(() => {
  vi.useFakeTimers();
  Object.defineProperty(document, "hidden", { configurable: true, value: false });
});

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

describe("the two tick rates", () => {
  it("beats every five seconds while there is no alert", async () => {
    const read = stubRead({ alerts: [], server_now: NOW , unread_notifications: 0 });
    await mount();
    expect(read).toHaveBeenCalledTimes(1);

    await advance(4_999);
    expect(read).toHaveBeenCalledTimes(1);
    await advance(1);
    expect(read).toHaveBeenCalledTimes(2);
  });

  it("beats every two seconds while ANY alert is live, including one that is not hers", async () => {
    // ⚠ THE CONDITION IS `{open, accepted}` AND NEVER `for_me`, and this row is
    // the raiser's own page: the overlay never rises for it (she knows, she
    // raised it) so `for_me` is false — and she is precisely the person waiting
    // to learn who is coming. Keyed on `for_me` she would wait five seconds for
    // «דנה כהן מגיעה.» while the acceptor's own screen updated in two.
    const read = stubRead({ alerts: [alertRow({ for_me: false })], server_now: NOW , unread_notifications: 0 });
    await mount();
    expect(read).toHaveBeenCalledTimes(1);

    await advance(1_999);
    expect(read).toHaveBeenCalledTimes(1);
    await advance(1);
    expect(read).toHaveBeenCalledTimes(2);
  });

  it("keeps the two-second beat while an alert is ACCEPTED and not yet resolved", async () => {
    // The acceptor is watching for the resolve and the raiser for the stall, so
    // an accepted alert is still a live one. Dropping back to five seconds here
    // is what would make the stall re-rise arrive late.
    const read = stubRead({
      alerts: [alertRow({ status: "accepted", acknowledged_at: NOW, for_me: false })],
      server_now: NOW,
    });
    await mount();
    await advance(2_000);
    expect(read).toHaveBeenCalledTimes(2);
  });

  it("switches on the tick that OBSERVES the first alert, not the one after (AC20b)", async () => {
    // ⚠ ONE REAL TICK. The gap is read at arm time from a ref the response
    // writes on the line above poll.succeeded() — both in the same microtask
    // chain, i.e. before React commits anything. Derive it from React state and
    // this tick re-arms at 5 000 and the 2-second cadence starts one tick late,
    // exactly when the raiser is waiting.
    const read = stubRead({ alerts: [], server_now: NOW , unread_notifications: 0 }, { alerts: [alertRow()], server_now: NOW , unread_notifications: 0 });
    await mount();
    expect(read).toHaveBeenCalledTimes(1);

    await advance(5_000);
    expect(read).toHaveBeenCalledTimes(2); // the tick that observes the alert

    await advance(1_999);
    expect(read).toHaveBeenCalledTimes(2);
    await advance(1);
    expect(read).toHaveBeenCalledTimes(3); // 2 000 later, NOT 5 000
  });

  it("goes back to five seconds once the last alert closes", async () => {
    const read = stubRead({ alerts: [alertRow()], server_now: NOW , unread_notifications: 0 }, { alerts: [], server_now: NOW , unread_notifications: 0 });
    await mount();
    await advance(2_000);
    expect(read).toHaveBeenCalledTimes(2); // the tick that observes the empty list

    await advance(4_999);
    expect(read).toHaveBeenCalledTimes(2);
    await advance(1);
    expect(read).toHaveBeenCalledTimes(3);
  });
});

describe("the idle stop, disabled", () => {
  it("never idle-stops (AC19)", async () => {
    // ⚠ THE MOST DANGEROUS LINE IN THE FEATURE IF IT IS GOT WRONG. Ten idle
    // minutes is right for a wall board and lethal for an emergency receiver:
    // a phone in an apron pocket would silently stop receiving pages, and
    // silence is the worst property an emergency channel can have.
    const read = stubRead({ alerts: [], server_now: NOW , unread_notifications: 0 });
    await mount();
    await advance(IDLE_STOP_MS + 60_000);

    const before = read.mock.calls.length;
    await advance(5_000);
    expect(read.mock.calls.length).toBe(before + 1);
  });
});

describe("the terminal rule, and a channel that never dies quietly", () => {
  it("a 401 stops the loop and ends the session EXACTLY ONCE", async () => {
    // ⚠ StrictMode, deliberately: main.tsx wraps <App/> in it, and its
    // setup -> cleanup -> setup cycle leaves TWO reads in flight against one
    // generation. Both classify the same 401. Without the once-guard the
    // console is dropped to the login form twice.
    const onSessionEnded = vi.fn();
    const read = stubRead();
    read.mockRejectedValue(new ApiError(401, "NOT_AUTHENTICATED", "no"));
    await mount({ onSessionEnded, strict: true });

    expect(onSessionEnded).toHaveBeenCalledTimes(1);
    expect(sos.terminal).toBe("session");

    const stoppedAt = read.mock.calls.length;
    await advance(60_000);
    expect(read.mock.calls.length).toBe(stoppedAt);
    expect(onSessionEnded).toHaveBeenCalledTimes(1);
  });

  it("a 403 is terminal ACCESS, reports the channel down and does NOT end the session", async () => {
    // ⚠ NOT a logout. A mid-shift demotion resolves its session fine and the
    // role gate refuses; dropping her to the login screen would be a lie, and
    // rendering nothing would leave a working-looking console over a dead
    // channel. The strip is the only app-level surface that can say so on the
    // eleven sections with no panel of their own.
    const onSessionEnded = vi.fn();
    const read = stubRead();
    read.mockRejectedValue(new ApiError(403, "NOT_AUTHORIZED", "no"));
    await mount({ onSessionEnded });

    expect(sos.terminal).toBe("access");
    expect(sos.channelDown).toBe(true);
    expect(onSessionEnded).not.toHaveBeenCalled();
  });

  it("reports the channel down once the loop has backed off beyond one tick", async () => {
    const read = stubRead();
    read.mockRejectedValue(new Error("network"));
    await mount();

    // One failed tick is a blip, and the console does not shout about a blip.
    expect(sos.channelDown).toBe(false);

    await advance(10_000); // the gap doubled; this is the second failure
    expect(read).toHaveBeenCalledTimes(2);
    expect(sos.channelDown).toBe(true);
  });

  it("KEEPS the alerts on screen when a tick fails", async () => {
    // ⚠ A DROPPED REQUEST IS NOT A RESOLVED EMERGENCY. Blanking the list on a
    // failed tick would take a live alert off every screen in the boutique for
    // as long as the network is bad, which is the silent loss this whole
    // feature exists to prevent — and it would do it while the strip below
    // says the channel is down, so nobody would look for the missing card.
    const read = stubRead({ alerts: [alertRow()], server_now: NOW , unread_notifications: 0 });
    await mount();
    expect(sos.alerts).toHaveLength(1);

    read.mockRejectedValue(new Error("network"));
    await advance(2_000);
    expect(read).toHaveBeenCalledTimes(2);
    expect(sos.alerts).toHaveLength(1);
  });

  it("clears the channel-down claim on the first tick that succeeds", async () => {
    const read = stubRead();
    read.mockRejectedValue(new Error("network"));
    await mount();
    await advance(10_000);
    expect(sos.channelDown).toBe(true);

    read.mockResolvedValue({ alerts: [], server_now: NOW , unread_notifications: 0 });
    await advance(20_000);
    expect(sos.channelDown).toBe(false);
  });
});

describe("the four actions", () => {
  it("patches the row from the ACCEPT's own response, before any tick", async () => {
    stubRead({ alerts: [alertRow()], server_now: NOW , unread_notifications: 0 });
    await mount();
    expect(sos.alerts[0].status).toBe("open");

    vi.spyOn(api, "acceptSos").mockResolvedValue(
      alertRow({ status: "accepted", accepted_by_name: "נועה לוי", acknowledged_at: NOW }),
    );
    await act(async () => {
      await sos.accept(ALERT_ID);
    });
    expect(sos.alerts[0].status).toBe("accepted");
    expect(sos.alerts[0].accepted_by_name).toBe("נועה לוי");
  });

  it("drops the row when a RESOLVE or a CANCEL closes it", async () => {
    stubRead({ alerts: [alertRow()], server_now: NOW , unread_notifications: 0 });
    await mount();

    vi.spyOn(api, "resolveSos").mockResolvedValue(alertRow({ status: "resolved" }));
    await act(async () => {
      await sos.resolve(ALERT_ID);
    });
    expect(sos.alerts).toHaveLength(0);
  });

  it("merges a RAISE's own alert at once, and hands the reroute fact back", async () => {
    // ⚠ The raiser's own page never rises in the overlay, and on the floor
    // section the board may be paused — so without this merge a staffer who
    // raised would see her own alert NOWHERE, with a transient cue as her only
    // feedback. `rerouted` is a fact about the REQUEST and cannot come from any
    // later read.
    stubRead({ alerts: [], server_now: NOW , unread_notifications: 0 });
    await mount();

    vi.spyOn(api, "raiseSos").mockResolvedValue({ alert: alertRow(), rerouted: true });
    let outcome: RaiseOutcome | undefined;
    await act(async () => {
      outcome = await sos.raise({});
    });
    expect(sos.alerts).toHaveLength(1);
    expect(outcome?.failure).toBeNull();
    expect(outcome?.raised?.rerouted).toBe(true);
  });

  it("re-arms at TWO seconds after a raise that created the first alert", async () => {
    // ⚠ The raiser is the person waiting hardest, and this is the one path
    // where the alert arrives without a tick having observed it. A successful
    // action is a round trip that worked, so it resets the backoff — and the
    // reset re-resolves the gap against the list the action just changed.
    // Without it her own raise keeps the five-second beat for one more tick.
    const read = stubRead({ alerts: [], server_now: NOW , unread_notifications: 0 });
    await mount();
    expect(read).toHaveBeenCalledTimes(1);

    vi.spyOn(api, "raiseSos").mockResolvedValue({ alert: alertRow(), rerouted: false });
    await act(async () => {
      await sos.raise({});
    });

    await advance(1_999);
    expect(read).toHaveBeenCalledTimes(1);
    await advance(1);
    expect(read).toHaveBeenCalledTimes(2);
  });

  it("issues no tick while an action is in flight and re-arms ONE when it settles", async () => {
    const read = stubRead({ alerts: [alertRow()], server_now: NOW , unread_notifications: 0 });
    await mount();
    expect(read).toHaveBeenCalledTimes(1);

    let settle: (value: SosAlert) => void = () => {};
    vi.spyOn(api, "acceptSos").mockReturnValue(
      new Promise<SosAlert>((resolve) => {
        settle = resolve;
      }),
    );
    let pending: Promise<unknown> | undefined;
    act(() => {
      pending = sos.accept(ALERT_ID);
    });

    // The armed tick was cancelled the moment the action started.
    await advance(10_000);
    expect(read).toHaveBeenCalledTimes(1);

    await act(async () => {
      settle(alertRow({ status: "accepted" }));
      await pending;
    });
    await advance(2_000);
    expect(read).toHaveBeenCalledTimes(2);
  });

  it("re-arms after a REFUSED action, or the channel stops converging the first time anybody acts", async () => {
    // ⚠ THE RE-ARM LIVES IN THE .finally() AND NOT ON THE SUCCESS PATH. A 409
    // is the ordinary outcome of two responders tapping «אני מגיעה» at once, so
    // parking the loop on it would stop the emergency channel of the person who
    // lost a race she did not lose anything by losing.
    const read = stubRead({ alerts: [alertRow()], server_now: NOW , unread_notifications: 0 });
    await mount();

    vi.spyOn(api, "acceptSos").mockRejectedValue(
      new ApiError(409, "SOS_ALREADY_ACCEPTED", "taken", { staff_display_name: "דנה כהן" }),
    );
    let failure: unknown;
    await act(async () => {
      failure = await sos.accept(ALERT_ID);
    });
    expect(failure).toBeInstanceOf(ApiError);
    expect((failure as ApiError).details).toEqual({ staff_display_name: "דנה כהן" });

    await advance(2_000);
    expect(read).toHaveBeenCalledTimes(2);
  });

  it("classifies an action's 401 through the same rule the ticks use", async () => {
    const onSessionEnded = vi.fn();
    stubRead({ alerts: [alertRow()], server_now: NOW , unread_notifications: 0 });
    await mount({ onSessionEnded });

    vi.spyOn(api, "cancelSos").mockRejectedValue(new ApiError(401, "NOT_AUTHENTICATED", "no"));
    let failure: unknown = "unset";
    await act(async () => {
      failure = await sos.cancel(ALERT_ID);
    });
    // Terminal means the caller has nothing left to render.
    expect(failure).toBeNull();
    expect(sos.terminal).toBe("session");
    expect(onSessionEnded).toHaveBeenCalledTimes(1);
  });
});

describe("the provider contract", () => {
  it("refuses to be consumed outside the provider", () => {
    expect(() => render(<Consumer />)).toThrow();
  });
});

/**
 * F35's bell. The count rides THIS tick and adds no timer of its own — which is
 * the feature's whole delivery decision, so it is pinned here by counting the
 * loops rather than described in a comment nobody runs.
 */
describe("the unread notification count", () => {
  it("arrives off the tick payload and updates with it", async () => {
    stubRead(
      { alerts: [], server_now: NOW, unread_notifications: 2 },
      { alerts: [], server_now: NOW, unread_notifications: 5 },
    );
    await mount();
    expect(sos.unreadNotifications).toBe(2);

    await advance(5_000);
    expect(sos.unreadNotifications).toBe(5);
  });

  it("adds no second request and no second loop", async () => {
    // ⚠ ZERO NEW TIMERS is the requirement, and this is what enforces it: the
    // count comes off the SAME response as the alerts, so the tick count and the
    // request count stay equal. A fetch-on-open or a second interval shows up
    // here immediately.
    const read = stubRead({ alerts: [], server_now: NOW, unread_notifications: 1 });
    await mount();
    expect(read).toHaveBeenCalledTimes(1);

    await advance(15_000);
    expect(read).toHaveBeenCalledTimes(4);
    expect(sos.unreadNotifications).toBe(1);
  });

  it("KEEPS its last value when a tick fails and never zeroes it", async () => {
    // Design §4 state K: never invent a count, never zero one. The app-wide
    // `sos.channelDown` strip already says the channel is dead; a bell that
    // silently dropped to 0 would say the opposite of what is true.
    const read = stubRead({ alerts: [], server_now: NOW, unread_notifications: 3 });
    await mount();
    expect(sos.unreadNotifications).toBe(3);

    read.mockRejectedValue(new ApiError(500, "INTERNAL", "boom"));
    await advance(5_000);
    expect(sos.unreadNotifications).toBe(3);

    await advance(60_000);
    expect(sos.unreadNotifications).toBe(3);
    expect(sos.channelDown).toBe(true);
  });

  it("takes the count from the mark-read response without waiting for a tick", async () => {
    stubRead({ alerts: [], server_now: NOW, unread_notifications: 4 });
    await mount();
    const mark = vi.spyOn(api, "markNotificationsRead").mockResolvedValue({ unread: 1 });

    await act(async () => {
      await sos.markRead(["a", "b"]);
    });

    expect(mark).toHaveBeenCalledWith(["a", "b"]);
    expect(sos.unreadNotifications).toBe(1);
  });

  it("leaves the count alone when the mark-read fails", async () => {
    // The BELL owns the optimistic zero and its rollback (it is the thing on
    // screen); the provider only ever publishes a number the server gave it, so
    // a failed write must not move it.
    stubRead({ alerts: [], server_now: NOW, unread_notifications: 4 });
    await mount();
    vi.spyOn(api, "markNotificationsRead").mockRejectedValue(new ApiError(500, "INTERNAL", "boom"));

    let failure: unknown = "unset";
    await act(async () => {
      failure = await sos.markRead(["a"]);
    });

    expect(failure).toBeInstanceOf(ApiError);
    expect(sos.unreadNotifications).toBe(4);
  });
});
