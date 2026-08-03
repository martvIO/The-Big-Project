import { useEffect, useRef, useState } from "react";
import { ApiError } from "../api";

// Extracted from BoardSection in F57, which is the SECOND caller — F34's D13
// named this exact reopening condition ("the day there is a second caller the
// extraction is mechanical and reviewed") and the floor-program review's
// "do not pre-extract" applies to F34, not here. The acceptance gate is that
// BoardSection.test.tsx passes with a ZERO-LINE DIFF.
//
// It lives in lib/ rather than beside a component for lib/booking.tsx's reason:
// a shared helper hung off either end of an import chain closes it into a cycle.

// P-1 / spec Q-1. One client constant: if the pilot or F29 says five seconds is
// too expensive, halving the load is this line and the UI does not change.
export const POLL_INTERVAL_MS = 5_000;
// D4(6)'s cap, doubling from the base. D3 declines a server-side read limiter
// on this router — there is no attacker, only a fleet of loyal boards pointed
// at a sick server — so the throttle has to be the client's or there is none.
export const MAX_BACKOFF_MS = 60_000;
// P-8, resolved by the implementation plan rather than by the user. NOT the
// prototype's 45 seconds: that window exists so the state is reachable in a
// review, and shipping it would read as a bug.
export const IDLE_STOP_MS = 600_000;
export const IDLE_STOP_MINUTES = IDLE_STOP_MS / 60_000;

export type PollMode = "running" | "paused" | "idle";
export type PollTerminal = "session" | "access";

/**
 * What one tick decided. ⚠ THREE-VALUED, and an earlier draft of D10 got this
 * wrong by claiming both early returns move into the caller with "byte-identical
 * behaviour, zero API". The shipped source contradicts that in two places, and
 * BoardSection.test.tsx covers NEITHER — so the zero-edit gate alone could go
 * green over a changed loop, on the one component in the console that has
 * already shipped two loop bugs.
 *
 *   void          the caller has taken over and will re-arm itself, from the
 *                 .finally() of whatever request it issued.
 *   "held"        a pointer is down: re-arm at the CURRENT, possibly backed-off
 *                 gap and leave the backoff alone. A clean tick would reset to
 *                 base, so a held tick during a backoff would fetch at 5s.
 *   "suppressed"  a mutation is in flight: arm NOTHING. The single re-arm is
 *                 that mutation's own .finally(). A clean tick would arm a timer
 *                 DURING the mutation.
 */
export type TickOutcome = void | "held" | "suppressed";

export interface PollOptions {
  /**
   * One tick. Receives the generation it was issued under so an async caller can
   * discard a stale result with `isCurrent`. The hook has already checked that
   * the loop is running and the tab is visible.
   */
  run: (generation: number) => TickOutcome;
  /**
   * Fired when the idle stop trips, so the caller can name the cause in its own
   * region. The difference between "I paused this" and "this paused itself" is
   * the whole difference between a control and a bug — which is why there are
   * two modes and not one.
   */
  onIdleStop?: () => void;
}

export interface Poll {
  mode: PollMode;
  terminal: PollTerminal | null;
  /** The generation a request should capture before awaiting. */
  generation: () => number;
  /** Whether a captured generation is still the live one. */
  isCurrent: (generation: number) => boolean;
  /** Invalidate every result currently in the air. */
  bump: () => void;
  /** A success: reset the backoff to the base interval. */
  succeeded: () => void;
  /** A non-terminal failure: double the backoff, capped. */
  failed: () => void;
  /** The `.finally()` re-arm, at the current gap. */
  reschedule: () => void;
  /** Cancel the armed timer without stopping the loop. */
  clearTick: () => void;
  /**
   * Classify an error. Returns true and STOPS the loop when it is terminal.
   * Used by ticks and by mutations alike — which is what makes a toggle's 403
   * terminal (deck P-6) one line rather than a second classifier.
   */
  fail: (error: unknown) => boolean;
  /** A fresh user intent: invalidate, cancel and fetch now. */
  refresh: () => void;
  pause: () => void;
  resume: () => void;
}

// The terminal set is {401, 403}, not {401}. Deactivation ends in a 401
// (staff_users.by_id filters deleted_at, resolve_session returns None); a
// mid-shift DEMOTION ends in a 403 (the session resolves fine and RoleGate
// raises). A loop that stopped only on the 401 would keep polling a revoked role
// forever while the demotion had no visible effect — silently defeating "a role
// change bites on the very next request" on the screens in the product that keep
// making requests after a revocation.
export function terminalOf(error: unknown): PollTerminal | null {
  if (!(error instanceof ApiError)) {
    return null;
  }
  if (error.status === 401) {
    return "session";
  }
  return error.status === 403 ? "access" : null;
}

export function usePoll({ run, onIdleStop }: PollOptions): Poll {
  const [mode, setMode] = useState<PollMode>("running");
  const [terminal, setTerminal] = useState<PollTerminal | null>(null);

  // The timer always calls the LATEST tick, so the loop reads current state
  // without a ref mirror of every field it needs.
  const tickRef = useRef<() => void>(() => {});
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const idleRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const backoffRef = useRef(POLL_INTERVAL_MS);
  // One monotonic generation. A poll applies its result only if the generation
  // it was issued under is unchanged; mutations, the date roll, the manual retry
  // and resume all bump it.
  const generationRef = useRef(0);
  const runningRef = useRef(true);
  const runRef = useRef(run);
  const idleStopRef = useRef(onIdleStop);

  useEffect(() => {
    runRef.current = run;
    idleStopRef.current = onIdleStop;
  });

  const clearTick = () => {
    if (timerRef.current !== null) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  };

  const clearIdle = () => {
    if (idleRef.current !== null) {
      clearTimeout(idleRef.current);
      idleRef.current = null;
    }
  };

  // THE ONE ARMING SITE. Every caller is a request's .finally() or a user
  // intent, which is what makes "at most one poll in flight per tab" a property
  // of the construction rather than of a flag somebody has to keep right.
  const schedule = (ms: number) => {
    clearTick();
    // document.hidden pauses the loop, and honestly rather than as an
    // optimisation: browsers already throttle background timers to >=1/minute,
    // so an unpaused loop would silently become a slow one and the screen would
    // look live while being a minute stale.
    if (!runningRef.current || document.hidden) {
      return;
    }
    timerRef.current = setTimeout(() => {
      timerRef.current = null;
      tickRef.current();
    }, ms);
  };

  const armIdle = () => {
    clearIdle();
    if (!runningRef.current) {
      return;
    }
    idleRef.current = setTimeout(() => {
      idleRef.current = null;
      runningRef.current = false;
      clearTick();
      setMode("idle");
      idleStopRef.current?.();
    }, IDLE_STOP_MS);
  };

  const stop = (next: PollTerminal) => {
    runningRef.current = false;
    clearTick();
    clearIdle();
    setTerminal(next);
  };

  const tick = () => {
    if (!runningRef.current || document.hidden) {
      return;
    }
    const outcome = runRef.current(generationRef.current);
    if (outcome === "held") {
      // Re-arm at the CURRENT gap and leave the backoff untouched.
      schedule(backoffRef.current);
      return;
    }
    // "suppressed" arms nothing at all; `void` means the caller re-arms from its
    // own request's .finally().
  };

  useEffect(() => {
    tickRef.current = tick;
  });

  useEffect(() => {
    runRef.current(generationRef.current);
    return () => {
      // ⚠ THE UNMOUNT FIX, moved here verbatim from BoardSection with its
      // comment. It was one of F34's two review blockers.
      //
      // clearTick() alone cancels only the timer armed RIGHT NOW. A request in
      // flight at unmount still reaches its .finally() and arms a fresh one, and
      // nothing in tick -> run -> finally -> reschedule touches React state, so
      // the loop would outlive the component forever — one orphan per nav-away.
      // This is also what makes "at most one poll in flight per tab by
      // construction" true rather than merely intended.
      //
      // Two callers today and four by F42. The alternative is this line being
      // copy-pasted four times by four different builders, or dropped by one.
      runningRef.current = false;
      clearTick();
      clearIdle();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const onVisibility = () => {
      if (document.hidden) {
        clearTick();
        return;
      }
      if (!runningRef.current) {
        return;
      }
      // Fetch at once rather than waiting out an interval: the screen is stale
      // by however long it was hidden, and five more seconds of a wrong screen
      // is the worst moment to add.
      generationRef.current += 1;
      clearTick();
      tickRef.current();
    };
    document.addEventListener("visibilitychange", onVisibility);
    return () => document.removeEventListener("visibilitychange", onVisibility);
  }, []);

  useEffect(() => {
    armIdle();
    const reset = () => armIdle();
    const types = ["pointerdown", "keydown", "focusin", "scroll"] as const;
    for (const type of types) {
      window.addEventListener(type, reset, { passive: true });
    }
    return () => {
      clearIdle();
      for (const type of types) {
        window.removeEventListener(type, reset);
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return {
    mode,
    terminal,
    generation: () => generationRef.current,
    isCurrent: (generation: number) => generation === generationRef.current,
    bump: () => {
      generationRef.current += 1;
    },
    succeeded: () => {
      backoffRef.current = POLL_INTERVAL_MS;
    },
    failed: () => {
      backoffRef.current = Math.min(backoffRef.current * 2, MAX_BACKOFF_MS);
    },
    reschedule: () => schedule(backoffRef.current),
    clearTick,
    fail: (error: unknown) => {
      const end = terminalOf(error);
      if (end === null) {
        return false;
      }
      stop(end);
      return true;
    },
    refresh: () => {
      generationRef.current += 1;
      clearTick();
      runRef.current(generationRef.current);
    },
    pause: () => {
      runningRef.current = false;
      clearTick();
      clearIdle();
      setMode("paused");
    },
    resume: () => {
      runningRef.current = true;
      setMode("running");
      // A resume is a fresh user intent, not a continuation of a backed-off
      // retry: a control that inherited a sixty-second gap would look like a
      // control that did not work.
      backoffRef.current = POLL_INTERVAL_MS;
      generationRef.current += 1;
      armIdle();
      clearTick();
      runRef.current(generationRef.current);
    },
  };
}
