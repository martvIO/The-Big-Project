import { useRef } from "react";
import { act, render } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "../api";
import {
  IDLE_STOP_MS,
  MAX_BACKOFF_MS,
  POLL_INTERVAL_MS,
  usePoll,
  terminalOf,
} from "../lib/usePoll";
import type { Poll, TickOutcome } from "../lib/usePoll";

/**
 * F57 extracts this loop from BoardSection, and `BoardSection.test.tsx` passing
 * with a ZERO-LINE DIFF is the acceptance gate for the six mechanisms.
 *
 * ⚠ THAT GATE IS NECESSARY AND NOT SUFFICIENT, which is what this file is for.
 * Two of the loop's behaviours are NOT covered by any of those 61 blocks — the
 * "held" tick's re-arm gap and the "suppressed" tick arming nothing — so the
 * zero-edit gate alone could go green over a changed loop, on the one component
 * in the console that has already shipped two loop bugs. Both are pinned by name
 * below, plus the unmount fix that was one of F34's two review blockers.
 */

// A harness component: drives the hook, records every tick, and exposes the Poll
// so a test can act on it the way a real caller would.
function Harness({
  outcome = () => undefined,
  onRun,
  expose,
}: {
  outcome?: () => TickOutcome;
  onRun?: (generation: number) => void;
  expose?: (poll: Poll) => void;
}) {
  const pollRef = useRef<Poll | null>(null);
  const poll = usePoll({
    run: (generation) => {
      onRun?.(generation);
      return outcome();
    },
  });
  pollRef.current = poll;
  expose?.(poll);
  return <div data-testid="mode">{poll.mode}</div>;
}

let runs: number[];
let poll: Poll;

function mount(options: { outcome?: () => TickOutcome } = {}) {
  runs = [];
  return render(
    <Harness
      outcome={options.outcome}
      onRun={(generation) => runs.push(generation)}
      expose={(value) => {
        poll = value;
      }}
    />,
  );
}

beforeEach(() => {
  vi.useFakeTimers();
  Object.defineProperty(document, "hidden", { configurable: true, value: false });
});

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

function advance(ms: number) {
  act(() => {
    vi.advanceTimersByTime(ms);
  });
}

function hide(hidden: boolean) {
  Object.defineProperty(document, "hidden", { configurable: true, value: hidden });
  act(() => {
    document.dispatchEvent(new Event("visibilitychange"));
  });
}

describe("the arming site", () => {
  it("runs once at mount and then once per interval, never two in flight", () => {
    mount();
    expect(runs).toHaveLength(1);

    act(() => poll.reschedule());
    advance(POLL_INTERVAL_MS);
    expect(runs).toHaveLength(2);

    // No second timer was armed by the tick itself — a `void` outcome means the
    // caller re-arms from its own request's .finally().
    advance(POLL_INTERVAL_MS * 3);
    expect(runs).toHaveLength(2);
  });

  it("re-arming twice replaces the timer rather than stacking two", () => {
    mount();
    act(() => {
      poll.reschedule();
      poll.reschedule();
    });
    advance(POLL_INTERVAL_MS);
    expect(runs).toHaveLength(2);
  });
});

describe("the unmount fix", () => {
  it("a request unresolved at unmount arms nothing", () => {
    // ⚠ F34's shipped review blocker, proven at the layer it now lives in.
    //
    // clearTick() alone cancels only the timer armed RIGHT NOW. A request in
    // flight at unmount still reaches its .finally() and arms a fresh one, and
    // nothing in the cycle touches React state — so the loop outlives the
    // component forever, one orphan per nav-away, for the rest of a 12-hour
    // shift. Switching nav sections mid-request is all it takes.
    const view = mount();
    expect(runs).toHaveLength(1);

    // The component goes away while a request is still in the air.
    const inFlight = poll;
    view.unmount();

    // The request now settles and does what every settled request does.
    act(() => inFlight.reschedule());
    advance(POLL_INTERVAL_MS * 10);

    expect(runs).toHaveLength(1);
  });

  it("a timer already armed at unmount never fires", () => {
    const view = mount();
    act(() => poll.reschedule());
    view.unmount();
    advance(POLL_INTERVAL_MS * 5);
    expect(runs).toHaveLength(1);
  });
});

describe("the document.hidden gate", () => {
  it("arms nothing while the tab is hidden", () => {
    mount();
    hide(true);
    act(() => poll.reschedule());
    advance(POLL_INTERVAL_MS * 4);
    expect(runs).toHaveLength(1);
  });

  it("fetches IMMEDIATELY when the tab comes back, not after an interval", () => {
    // The screen is stale by however long it was hidden; five more seconds of a
    // wrong screen is the worst moment to add.
    mount();
    hide(true);
    expect(runs).toHaveLength(1);

    hide(false);
    expect(runs).toHaveLength(2);
  });

  it("does not fetch on unhide once the loop has stopped", () => {
    mount();
    act(() => poll.pause());
    hide(true);
    hide(false);
    expect(runs).toHaveLength(1);
  });
});

describe("the backoff", () => {
  it("doubles on consecutive failures and caps", () => {
    mount();
    act(() => {
      poll.failed();
      poll.reschedule();
    });
    advance(POLL_INTERVAL_MS);
    expect(runs).toHaveLength(1); // not yet — the gap is now 10s
    advance(POLL_INTERVAL_MS);
    expect(runs).toHaveLength(2);

    // Drive it past the cap and confirm it stops growing.
    act(() => {
      for (let i = 0; i < 20; i += 1) {
        poll.failed();
      }
      poll.reschedule();
    });
    advance(MAX_BACKOFF_MS - 1);
    expect(runs).toHaveLength(2);
    advance(1);
    expect(runs).toHaveLength(3);
  });

  it("one success resets the gap to the base interval", () => {
    mount();
    act(() => {
      poll.failed();
      poll.failed();
      poll.succeeded();
      poll.reschedule();
    });
    advance(POLL_INTERVAL_MS);
    expect(runs).toHaveLength(2);
  });
});

describe("the terminal classification", () => {
  // TWO tests, not one, and the paths genuinely differ: deactivation ends in a
  // 401 (resolve_session returns None) while a mid-shift DEMOTION ends in a 403
  // (the session resolves fine and RoleGate raises).
  it("a 401 stops the loop and reports session", () => {
    mount();
    let stopped = false;
    act(() => {
      stopped = poll.fail(new ApiError(401, "NOT_AUTHENTICATED", "no"));
    });
    expect(stopped).toBe(true);
    expect(poll.terminal).toBe("session");

    act(() => poll.reschedule());
    advance(POLL_INTERVAL_MS * 5);
    expect(runs).toHaveLength(1);
  });

  it("a 403 stops the loop and reports access", () => {
    mount();
    let stopped = false;
    act(() => {
      stopped = poll.fail(new ApiError(403, "NOT_AUTHORIZED", "no"));
    });
    expect(stopped).toBe(true);
    expect(poll.terminal).toBe("access");

    act(() => poll.reschedule());
    advance(POLL_INTERVAL_MS * 5);
    expect(runs).toHaveLength(1);
  });

  it("fail() classifies a mutation's error the same way and anything else as not terminal", () => {
    // This is deck P-6's whole mechanism: a break toggle answering 403 is
    // terminal, via the SAME rule the ticks use rather than a second classifier.
    mount();
    let stopped = true;
    act(() => {
      stopped = poll.fail(new ApiError(409, "BOOKING_TRANSITION_INVALID", "no"));
    });
    expect(stopped).toBe(false);
    expect(poll.terminal).toBeNull();

    act(() => {
      stopped = poll.fail(new Error("network"));
    });
    expect(stopped).toBe(false);
    expect(poll.terminal).toBeNull();
  });

  it("terminalOf reads only ApiError statuses", () => {
    expect(terminalOf(new ApiError(401, "x", "x"))).toBe("session");
    expect(terminalOf(new ApiError(403, "x", "x"))).toBe("access");
    expect(terminalOf(new ApiError(500, "x", "x"))).toBeNull();
    expect(terminalOf(new Error("nope"))).toBeNull();
    expect(terminalOf("nope")).toBeNull();
  });
});

describe("pause and resume", () => {
  it("pause stops the loop", () => {
    mount();
    act(() => poll.pause());
    expect(poll.mode).toBe("paused");
    act(() => poll.reschedule());
    advance(POLL_INTERVAL_MS * 5);
    expect(runs).toHaveLength(1);
  });

  it("resume fetches immediately and at the BASE gap, not a backed-off one", () => {
    // A resume is a fresh user intent, not a continuation of a backed-off retry:
    // a control that inherited a sixty-second gap would look like a control that
    // did not work.
    mount();
    act(() => {
      poll.failed();
      poll.failed();
      poll.failed();
      poll.pause();
    });
    expect(runs).toHaveLength(1);

    act(() => poll.resume());
    expect(poll.mode).toBe("running");
    expect(runs).toHaveLength(2); // immediate, before any interval elapsed

    act(() => poll.reschedule());
    advance(POLL_INTERVAL_MS);
    expect(runs).toHaveLength(3); // and at the base gap
  });

  it("resume invalidates whatever was in the air", () => {
    mount();
    const before = poll.generation();
    act(() => poll.resume());
    expect(poll.isCurrent(before)).toBe(false);
  });
});

describe("the idle stop", () => {
  it("fires after the idle window and stops the loop", () => {
    mount();
    advance(IDLE_STOP_MS);
    expect(poll.mode).toBe("idle");

    act(() => poll.reschedule());
    advance(POLL_INTERVAL_MS * 5);
    expect(runs).toHaveLength(1);
  });

  it("one interaction resets the window", () => {
    mount();
    advance(IDLE_STOP_MS - 1000);
    act(() => {
      window.dispatchEvent(new Event("keydown"));
    });
    advance(2000);
    expect(poll.mode).toBe("running");

    advance(IDLE_STOP_MS);
    expect(poll.mode).toBe("idle");
  });

  it("calls onIdleStop so the caller can name the cause", () => {
    const onIdleStop = vi.fn();
    render(<Harness expose={(value) => (poll = value)} />);
    // A second, isolated mount with the callback wired.
    const named = vi.fn();
    function Named() {
      usePoll({ run: () => undefined, onIdleStop: named });
      return null;
    }
    render(<Named />);
    advance(IDLE_STOP_MS);
    expect(named).toHaveBeenCalledTimes(1);
    expect(onIdleStop).not.toHaveBeenCalled();
  });
});

describe("the two TickOutcome divergences the zero-edit gate cannot see", () => {
  it('a "held" tick re-arms at the BACKED-OFF gap and does not reset it', () => {
    // ⚠ Not covered by any of BoardSection.test.tsx's 61 blocks. The shipped
    // board re-arms a held tick with `schedule(backoffRef.current)` — the
    // CURRENT, possibly backed-off gap, backoff untouched. If the hook treated a
    // hold as a clean tick it would reset to base, and a held tick during a
    // backoff would start fetching at 5s against a server already failing.
    let held = true;
    mount({ outcome: () => (held ? "held" : undefined) });

    // Back the interval off to 20s, then let a held tick fire.
    act(() => {
      poll.failed();
      poll.failed();
      poll.reschedule();
    });
    advance(POLL_INTERVAL_MS * 4); // 20s
    expect(runs).toHaveLength(2); // the held tick ran

    // The hook re-armed it. If the gap had been reset to base, the next run
    // would land at 5s.
    held = false;
    advance(POLL_INTERVAL_MS);
    expect(runs).toHaveLength(2);
    advance(POLL_INTERVAL_MS * 3);
    expect(runs).toHaveLength(3);
  });

  it('a "suppressed" tick arms no timer at all', () => {
    // ⚠ Also uncovered by the zero-edit gate. The shipped board returns from
    // tick() with NO schedule() while a mutation is in flight; the single re-arm
    // is that mutation's own .finally(). A clean-tick re-arm here would arm
    // timers DURING a mutation.
    mount({ outcome: () => "suppressed" });
    act(() => poll.reschedule());
    advance(POLL_INTERVAL_MS);
    expect(runs).toHaveLength(2); // the suppressed tick ran

    // …and armed nothing.
    advance(POLL_INTERVAL_MS * 10);
    expect(runs).toHaveLength(2);
  });
});

describe("generations", () => {
  it("bump invalidates a captured generation", () => {
    mount();
    const captured = poll.generation();
    expect(poll.isCurrent(captured)).toBe(true);
    act(() => poll.bump());
    expect(poll.isCurrent(captured)).toBe(false);
  });

  it("refresh invalidates, cancels and fetches now", () => {
    mount();
    const captured = poll.generation();
    act(() => {
      poll.reschedule();
      poll.refresh();
    });
    expect(runs).toHaveLength(2);
    expect(poll.isCurrent(captured)).toBe(false);

    // The timer refresh cancelled did not also fire.
    advance(POLL_INTERVAL_MS * 3);
    expect(runs).toHaveLength(2);
  });
});
