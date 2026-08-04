import { useRef, useState } from "react";
import type { ReactNode } from "react";
import { api, type RaisedAlert, type SosAlert } from "../api";
import { SosContext, type SosContextValue } from "./sos-context";
import { terminalOf, usePoll, type TickOutcome } from "./usePoll";

/**
 * The app-level emergency channel: one poll, one alert list, two consumers.
 *
 * ⚠ A PROVIDER RATHER THAN STATE IN `App`, AND THE FORCING CONSTRAINT IS
 * MECHANICAL. `App` early-returns for `!bootstrapped` and again for a signed-out
 * staffer, so a hook called after those returns is a rules-of-hooks violation —
 * and `.oxlintrc.json` sets `react/rules-of-hooks: error` precisely so that is a
 * lint failure rather than a runtime one. A provider is a component boundary, so
 * it may be mounted CONDITIONALLY where a hook may not. `ToastProvider` is the
 * shipped precedent and is already wrapped around the same tree.
 *
 * ⚠ A SEPARATE LOOP FROM `FloorPanel`'s, AND FOLDING IS REFUSED ON FOUR
 * INDEPENDENTLY SUFFICIENT GROUNDS: the overlay must render over ANY section and
 * `FloorPanel` mounts on 2 of 13; folding would put a customer's name on an
 * app-level loop; it would require lifting floor state above `FloorPanel`; and
 * the two need different tick rates and different idle behaviour — one loop
 * cannot be both 5s-fixed-and-idle-stopping and 5s/2s-and-never-stopping.
 *
 * The two loops do not coordinate and must not. They are independent `usePoll`
 * instances with independent generations, backoffs and terminal states. The only
 * place they touch is the board's pause, which is a RENDERING contract inside
 * `SosCentre` and not a poll-to-poll link: pausing a VIEW must never disable the
 * CHANNEL.
 *
 * ⚠ THREE LOOPS ON THE BOARD SCREEN IS THIS ARCHITECTURE'S CEILING. If a fifth
 * `usePoll` caller ever appears, that is the moment to ask whether the console
 * wants one multiplexed poll rather than N.
 */

// Per SOS tick, per device: 3 sessions opened, 2 set_config + BEGIN/COMMIT, 3
// pool pre-pings, 4 business SQL — ~6 statements and ~11 round trips, identical
// to the floor tick because the alerts read is ONE statement. On the board
// screen that takes the total from ~30 to ~41 per 5s idle and ~57 while an alert
// is open, and ELEVEN SECTIONS THAT POLLED NOTHING NOW POLL.
export const SOS_INTERVAL_MS = 5_000;
// Pre-authorised: the SOS feed is one row, so it may beat faster than the
// board's five seconds. The raiser is watching for the accept, the acceptor for
// the resolve, and the shift manager for the stall.
export const SOS_ALERT_INTERVAL_MS = 2_000;

// One failed tick is a blip and the console does not shout about a blip. Beyond
// that the gap has already doubled at least once, and «nothing renders» is not
// an acceptable state for an emergency receiver that has stopped receiving.
const CHANNEL_DOWN_AFTER_FAILURES = 1;

function isLive(alert: SosAlert): boolean {
  return alert.status === "open" || alert.status === "accepted";
}

export function SosProvider({
  onSessionEnded,
  children,
}: {
  /**
   * ⚠ Fired EXACTLY ONCE on a 401, and it is the whole of «the receiving end
   * never dies silently». `App` clears `staff` in exactly two places today and
   * there is no fetch interceptor, so without this callback the console keeps
   * rendering normally on eleven sections that poll nothing else while the
   * emergency channel is dead and says so nowhere.
   */
  onSessionEnded?: () => void;
  children: ReactNode;
}) {
  const [alerts, setAlerts] = useState<SosAlert[]>([]);
  const [serverNow, setServerNow] = useState<string | null>(null);
  const [failures, setFailures] = useState(0);

  // ⚠ THE GAP IS DERIVED FROM THE RESPONSE AND NEVER FROM REACT STATE. The tick
  // writes this on the line above poll.succeeded(), in the same microtask chain
  // as the response — so `intervalMs` resolves to 2 000 on the tick that
  // OBSERVES the first alert. A state-derived gap re-arms that tick at 5 000 and
  // starts the fast cadence one tick late, precisely when the raiser is waiting
  // to see who is coming.
  const hasLiveAlertRef = useRef(false);
  const tickRef = useRef<() => TickOutcome>(() => undefined);
  const mutationsRef = useRef(0);
  const sessionEndedRef = useRef(false);
  const onSessionEndedRef = useRef(onSessionEnded);
  onSessionEndedRef.current = onSessionEnded;

  const poll = usePoll({
    run: () => tickRef.current(),
    intervalMs: () => (hasLiveAlertRef.current ? SOS_ALERT_INTERVAL_MS : SOS_INTERVAL_MS),
    // ⚠ THE IDLE STOP IS DISABLED, AND THIS IS THE MOST DANGEROUS LINE IN THE
    // FEATURE IF IT IS GOT WRONG. Ten minutes of no pointer, key, focus or
    // scroll is exactly right for a wall board and lethal here: a phone in an
    // apron pocket, untouched for eleven minutes, would SILENTLY STOP RECEIVING
    // PAGES, and silence is the worst property an emergency channel can have.
    //
    // SC 2.2.2 does not bind. In the idle state this renders nothing at all, so
    // there is no auto-updating content to pause. In the alert state nothing
    // auto-updates — one card per alert, static text, an ABSOLUTE time, no
    // countdown and no live counter, which the design forbids and which is what
    // keeps this true rather than merely claimed. And the "hide" mechanism the
    // criterion asks for exists: the dismiss control, plus Esc.
    //
    // The `document.hidden` pause inside `usePoll` still applies and is KEPT
    // deliberately — a backgrounded tab's timers are throttled by the browser
    // anyway, so an unpaused loop would become a slow one that looked live.
    idleStopMs: null,
  });

  // ⚠ Classified HERE and not in an effect, and the guard is load-bearing:
  // StrictMode's setup -> cleanup -> setup leaves two reads in flight against
  // one generation, and a mutation can settle beside a tick. Both would drop the
  // console to the login form.
  const failTerminally = (error: unknown): boolean => {
    if (terminalOf(error) === "session" && !sessionEndedRef.current) {
      sessionEndedRef.current = true;
      onSessionEndedRef.current?.();
    }
    return poll.fail(error);
  };

  const merge = (alert: SosAlert) => {
    setAlerts((current) => {
      if (!isLive(alert)) {
        return current.filter((one) => one.id !== alert.id);
      }
      if (current.some((one) => one.id === alert.id)) {
        return current.map((one) => (one.id === alert.id ? alert : one));
      }
      // A row this device just created is the newest, so appending keeps the
      // oldest-first order the read establishes. The next tick re-sorts anyway.
      return [...current, alert];
    });
    hasLiveAlertRef.current = hasLiveAlertRef.current || isLive(alert);
  };

  const load = async () => {
    const generation = poll.generation();
    try {
      const result = await api.getSos();
      if (!poll.isCurrent(generation)) {
        return;
      }
      // ⚠ ONE REF WRITE, ON THE LINE ABOVE succeeded(). See hasLiveAlertRef.
      hasLiveAlertRef.current = result.alerts.some(isLive);
      setAlerts(result.alerts);
      setServerNow(result.server_now);
      setFailures(0);
      poll.succeeded();
    } catch (error) {
      if (!poll.isCurrent(generation)) {
        return;
      }
      if (failTerminally(error)) {
        return;
      }
      // Alerts already on screen are KEPT: an emergency does not stop being one
      // because a request dropped, and blanking the list would be the same
      // silent loss the feature exists to prevent.
      setFailures((count) => count + 1);
      poll.failed();
    } finally {
      if (poll.isCurrent(generation) && mutationsRef.current === 0) {
        poll.reschedule();
      }
    }
  };

  const tick = (): TickOutcome => {
    if (mutationsRef.current > 0) {
      return "suppressed";
    }
    void load();
  };

  // Assigned during render, not in an effect: usePoll's mount effect runs before
  // any effect here, so an effect-assigned ref would still hold its placeholder
  // when the hook fires the FIRST read.
  tickRef.current = tick;

  /**
   * The poll bookkeeping every action needs identically — the shipped floor
   * panel's five-part dance, copied rather than imported because importing it
   * would couple an app-level provider to a component mounted on 2 of 13
   * sections.
   *
   * ⚠ THE RE-ARM LIVES IN THE `.finally()` AND NOT ON THE SUCCESS PATH. A 409 is
   * the ORDINARY outcome of two responders tapping «אני מגיעה» at once, so
   * parking the loop on it would stop the emergency channel of the person who
   * lost a race she lost nothing by losing.
   *
   * Returns `null` when the call succeeded OR was terminal (both mean the caller
   * has nothing left to render) and the error otherwise: a 409 naming the owner
   * and a 404 are different Hebrew sentences, so mapping one is the caller's job.
   */
  const mutate = async (run: () => Promise<void>): Promise<unknown> => {
    mutationsRef.current += 1;
    poll.clearTick();
    poll.bump();
    try {
      await run();
      // A round trip that worked, so the backoff resets — and with it the gap
      // re-resolves against the list this action just changed. Without it a
      // raise that creates the first alert would keep the five-second beat for
      // one more tick, on the device whose staffer is waiting hardest.
      poll.succeeded();
      return null;
    } catch (error) {
      if (failTerminally(error)) {
        return null;
      }
      return error;
    } finally {
      mutationsRef.current -= 1;
      if (mutationsRef.current === 0) {
        poll.reschedule();
      }
    }
  };

  const value: SosContextValue = {
    alerts,
    serverNow,
    terminal: poll.terminal,
    channelDown: poll.terminal === "access" || failures > CHANNEL_DOWN_AFTER_FAILURES,
    raise: async (body) => {
      let raised: RaisedAlert | null = null;
      const failure = await mutate(async () => {
        raised = await api.raiseSos(body);
        merge(raised.alert);
      });
      return { raised, failure };
    },
    accept: (alertId) =>
      mutate(async () => {
        merge(await api.acceptSos(alertId));
      }),
    resolve: (alertId) =>
      mutate(async () => {
        merge(await api.resolveSos(alertId));
      }),
    cancel: (alertId) =>
      mutate(async () => {
        merge(await api.cancelSos(alertId));
      }),
  };

  return <SosContext.Provider value={value}>{children}</SosContext.Provider>;
}
