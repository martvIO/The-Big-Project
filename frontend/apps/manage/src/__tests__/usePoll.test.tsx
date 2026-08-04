import { StrictMode, useRef } from "react";
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
 * The "held" tick's re-arm gap is not covered by any of those 61 blocks, so the
 * zero-edit gate alone could go green over a changed loop, on the one component
 * in the console that has already shipped two loop bugs. It is pinned by name
 * below, with the unmount fix that was one of F34's two review blockers and the
 * mount effect's idempotence.
 *
 * ⚠ THE "suppressed" OUTCOME IS NOT PINNED HERE, and an earlier version of this
 * docstring claimed it was. INSIDE THE HOOK, "suppressed" and `void` take the
 * identical empty branch — neither arms anything — so no line of usePoll.ts can
 * be deleted to redden a "suppressed" test, and the case below is byte-equivalent
 * to the `void` one already covered by "runs once at mount and then once per
 * interval". The third union member is a CALLER contract, and the mechanism lives
 * in FloorPanel: `mutationsRef.current > 0 -> "suppressed"`. It is pinned in
 * FloorPanel.test.tsx ("suppresses every tick while a toggle is in flight"),
 * against the visibilitychange refetch — one of the TWO callers that invoke the
 * tick directly rather than through the timer (the other is poll.refresh(),
 * behind «רענון»), which is what lets either arrive mid-mutation once toggle()
 * has cleared the armed timer. The guard lives in FloorPanel's tick() rather
 * than at either call site precisely because there are two.
 */

// A harness component: drives the hook, records every tick, and exposes the Poll
// so a test can act on it the way a real caller would.
//
// F37 adds `intervalMs` and `idleStopMs` as PASS-THROUGHS. Omitting either is
// byte-identical to the shipped harness, which is what keeps every block above
// and below unedited (AC20).
function Harness({
  outcome = () => undefined,
  onRun,
  expose,
  intervalMs,
  idleStopMs,
}: {
  outcome?: () => TickOutcome;
  onRun?: (generation: number) => void;
  expose?: (poll: Poll) => void;
  intervalMs?: number | (() => number);
  idleStopMs?: number | null;
}) {
  const pollRef = useRef<Poll | null>(null);
  const poll = usePoll({
    run: (generation) => {
      onRun?.(generation);
      return outcome();
    },
    intervalMs,
    idleStopMs,
  });
  pollRef.current = poll;
  expose?.(poll);
  return <div data-testid="mode">{poll.mode}</div>;
}

let runs: number[];
let poll: Poll;

function mount(
  options: {
    outcome?: () => TickOutcome;
    intervalMs?: number | (() => number);
    idleStopMs?: number | null;
  } = {},
) {
  runs = [];
  return render(
    <Harness
      outcome={options.outcome}
      intervalMs={options.intervalMs}
      idleStopMs={options.idleStopMs}
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

describe("the mount effect is idempotent", () => {
  it("keeps polling after a StrictMode setup -> cleanup -> setup cycle", () => {
    // ⚠ REGRESSION. The cleanup sets runningRef false and nothing but resume()
    // ever sets it true, so without a re-arm at the top of the effect body a
    // second setup leaves the loop permanently dead: schedule() returns early on
    // every re-arm and armIdle() never arms, while `mode` stays "running" so the
    // UI shows a pause control for a loop that is not polling.
    //
    // main.tsx wraps <App/> in <StrictMode>, which performs exactly this cycle
    // on every mount in development. BoardSection has carried the same shape
    // since F34, so this one line fixes both callers.
    runs = [];
    render(
      <StrictMode>
        <Harness
          onRun={(generation) => runs.push(generation)}
          expose={(value) => {
            poll = value;
          }}
        />
      </StrictMode>,
    );
    const afterMount = runs.length;

    act(() => poll.reschedule());
    advance(POLL_INTERVAL_MS);

    expect(runs.length).toBeGreaterThan(afterMount);
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
    // Documents the hook's half of the contract: a "suppressed" outcome arms
    // nothing. ⚠ NOT a mutation target — see the file docstring: inside the hook
    // this is byte-equivalent to the `void` case, and the mechanism that makes it
    // matter is FloorPanel's, pinned there.
    mount({ outcome: () => "suppressed" });
    act(() => poll.reschedule());
    advance(POLL_INTERVAL_MS);
    expect(runs).toHaveLength(2); // the suppressed tick ran

    // …and armed nothing.
    advance(POLL_INTERVAL_MS * 10);
    expect(runs).toHaveLength(2);
  });
});

describe("F37: intervalMs, and the five-second hole the obvious test walks past", () => {
  it("governs the gap as a NUMBER", () => {
    mount({ intervalMs: 2_000 });
    act(() => poll.reschedule());
    advance(1_999);
    expect(runs).toHaveLength(1);
    advance(1);
    expect(runs).toHaveLength(2);
  });

  it("governs the gap as a FUNCTION, resolved when succeeded() is CALLED", () => {
    // The function form's whole point: the value is read at the moment the tick
    // resolves, not at the last React commit. Nothing re-renders between the
    // write below and succeeded(), which is exactly the shipped tick's shape.
    let gap = 5_000;
    mount({ intervalMs: () => gap });
    gap = 2_000;
    act(() => {
      poll.succeeded();
      poll.reschedule();
    });
    advance(1_999);
    expect(runs).toHaveLength(1);
    advance(1);
    expect(runs).toHaveLength(2);
  });

  it("succeeded() resets the backoff to the RESOLVED interval, not POLL_INTERVAL_MS", () => {
    // The shipped line was `backoffRef.current = POLL_INTERVAL_MS`. Left as it
    // was, the SOS loop's first successful tick would silently promote its
    // 2-second cadence back to five.
    mount({ intervalMs: 2_000 });
    act(() => {
      poll.failed();
      poll.failed();
      poll.succeeded();
      poll.reschedule();
    });
    advance(1_999);
    expect(runs).toHaveLength(1);
    advance(1);
    expect(runs).toHaveLength(2);
  });

  it("resume() resets to the RESOLVED interval too", () => {
    mount({ intervalMs: 2_000 });
    act(() => {
      poll.failed();
      poll.failed();
      poll.pause();
    });
    act(() => poll.resume());
    expect(runs).toHaveLength(2); // immediate
    act(() => poll.reschedule());
    advance(1_999);
    expect(runs).toHaveLength(2);
    advance(1);
    expect(runs).toHaveLength(3);
  });

  it("switches the gap on the tick that OBSERVES the change, not the one after (AC20b)", () => {
    // ⚠ ONE REAL TICK, and this is the block the weaker one below passes over.
    //
    // The shipped tick shape calls succeeded() inside the fetch's try and
    // reschedule() in its .finally() — both in the SAME microtask chain as the
    // response, i.e. before React commits anything. So a gap mirrored at commit
    // time makes the tick that first observes an alert re-arm at 5 000 ms and
    // the 2-second cadence start only on the tick AFTER — precisely when the
    // raiser is waiting to see who is coming.
    const hasAlert = { current: false };
    runs = [];
    render(
      <Harness
        intervalMs={() => (hasAlert.current ? 2_000 : 5_000)}
        onRun={(generation) => {
          runs.push(generation);
          if (runs.length === 2) {
            // This tick's response carries the first alert. The ref write sits
            // on the line above succeeded(), which is where SosProvider's does.
            hasAlert.current = true;
          }
          poll.succeeded();
          poll.reschedule();
        }}
        expose={(value) => {
          poll = value;
        }}
      />,
    );
    expect(runs).toHaveLength(1);

    advance(4_999);
    expect(runs).toHaveLength(1);
    advance(1);
    expect(runs).toHaveLength(2); // the tick that observes the alert

    advance(1_999);
    expect(runs).toHaveLength(2);
    advance(1);
    expect(runs).toHaveLength(3); // 2 000 ms later, NOT 5 000
  });

  it("takes a changed interval on the next re-arm — the weaker shape, kept deliberately", () => {
    // ⚠ THIS BLOCK IS KEPT BECAUSE IT IS THE ONE THAT WOULD HAVE SHIPPED THE
    // BUG. It re-renders the hook with a new prop and THEN ticks, so a gap
    // mirrored at commit time passes it. It is here in addition to the block
    // above and never instead of it; if this one ever becomes the only
    // interval test, AC20b is unpinned.
    runs = [];
    const props = {
      onRun: (generation: number) => runs.push(generation),
      expose: (value: Poll) => {
        poll = value;
      },
    };
    const view = render(<Harness intervalMs={5_000} {...props} />);
    view.rerender(<Harness intervalMs={2_000} {...props} />);
    act(() => {
      poll.succeeded();
      poll.reschedule();
    });
    advance(2_000);
    expect(runs).toHaveLength(2);
  });
});

describe("F37: idleStopMs, and an emergency receiver that must not stop receiving", () => {
  it("the default path is unchanged: POLL_INTERVAL_MS and IDLE_STOP_MS (AC20a)", () => {
    // ⚠ MECHANICAL, not a review instruction. Every shipped caller passes
    // neither field, so this block is the one that proves the two defaults are
    // still the two constants.
    mount();
    act(() => {
      poll.succeeded();
      poll.reschedule();
    });
    advance(POLL_INTERVAL_MS - 1);
    expect(runs).toHaveLength(1);
    advance(1);
    expect(runs).toHaveLength(2);

    advance(IDLE_STOP_MS);
    expect(poll.mode).toBe("idle");
  });

  it("null never idle-stops (AC19)", () => {
    mount({ idleStopMs: null });
    advance(IDLE_STOP_MS * 3);
    expect(poll.mode).toBe("running");

    act(() => poll.reschedule());
    advance(POLL_INTERVAL_MS);
    expect(runs).toHaveLength(2);
  });

  it("a timer already armed under a numeric gap does not survive the switch to null", () => {
    // ⚠ THE ORDERING RULE, and it is the whole of D12's second trap. armIdle()
    // opens with clearIdle(); put the null return ABOVE that call and the timer
    // armed under the numeric gap is never cancelled, so the loop still
    // idle-stops after the caller disabled the stop — a phone in an apron
    // pocket that silently stops receiving pages.
    runs = [];
    const props = {
      onRun: (generation: number) => runs.push(generation),
      expose: (value: Poll) => {
        poll = value;
      },
    };
    const view = render(<Harness idleStopMs={IDLE_STOP_MS} {...props} />);
    advance(IDLE_STOP_MS - 1_000); // a timer is armed and nearly due
    expect(poll.mode).toBe("running");

    view.rerender(<Harness idleStopMs={null} {...props} />);
    act(() => {
      window.dispatchEvent(new Event("keydown"));
    });

    advance(IDLE_STOP_MS * 2);
    expect(poll.mode).toBe("running");
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
