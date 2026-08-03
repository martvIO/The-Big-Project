import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Button, ButtonLink, JERusalem, Skeleton, VisuallyHidden, cn } from "@boutique/ui";
import { api, isNotFound } from "../api";
import type { TicketView } from "../api";
import { clearCheckinTicket } from "../lib/checkinTicket";

// The live position view: /q/{ticket_id}, opened by the create's own navigation
// or by the courtesy pointer on /checkin.
//
// The ticket id IS the capability — it is issued once, at creation, to the
// creating device — so this page holds no session, sends no cookie, and the
// response it polls echoes no personal detail about anybody, her included.
//
// Identical container to /book/*, /b/{token} and /checkin so the surfaces read
// as one product. hasBookingBar() is catalog-and-dress only, so this route
// reserves no CTA space; the block-end padding is the fixed A11y trigger's own
// footprint.
const pageClass = "mx-auto flex max-w-[640px] flex-col gap-6 px-4 pt-8 pb-16 md:px-6";

// P-1. One client constant: if the pilot says five seconds is too expensive,
// halving the load is this line and the UI does not change.
const POLL_INTERVAL_MS = 5_000;
// The cap, doubling from the base. There IS a server-side per-client ceiling
// here (30 reads / 60s per ticket) but it is 2.5x a healthy poll, so an outage
// still means every open ticket page retrying every five seconds against a sick
// server until it trips. The client backoff is the control; the server budget
// is the floor under a client that forgets to have one.
const MAX_BACKOFF_MS = 60_000;

// D10's success-terminal, and it has no HTTP analogue at all: a 200 ends the
// loop. Nothing in F33 writes either value — every transition is F58's — so
// until that ships this branch is unreachable in production and every open tab
// polls until it closes. That is Ruling 4's deployment gate, not a defect here.
const CLOSED_STATUSES = new Set(["done", "removed"]);

// Multi-line on purpose: qa-greps.sh flags a single-line Intl.DateTimeFormat
// without a timeZone, and a formatter built without one reads the DEVICE clock.
// The freshness claim is about the boutique's clock, the same choice the manage
// board and the confirmation screen make.
const TIME = new Intl.DateTimeFormat("en-GB", {
  timeZone: JERusalem,
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
});

type View =
  | { kind: "loading" }
  | { kind: "live"; ticket: TicketView }
  // A 404 or a malformed id — the ticket is unknown, swept or mistyped, and no
  // amount of retrying will change that.
  | { kind: "notFound" }
  // 429 / 5xx / network before anything has ever loaded. Recoverable, so it
  // offers a retry; the loop is still running underneath it.
  | { kind: "failed" };

function Heading({ children }: { children: string }) {
  return (
    <div className="flex flex-col gap-3">
      <h1 className="font-display text-2xl text-ink">{children}</h1>
      {/* The gold hairline every non-catalog route carries. */}
      <span aria-hidden="true" className="h-px w-12 bg-gold" />
    </div>
  );
}

export function QueuePositionPage({ ticketId }: { ticketId: string }) {
  const { t } = useTranslation();

  const [view, setView] = useState<View>({ kind: "loading" });
  const [updatedAt, setUpdatedAt] = useState<string | null>(null);
  const [stale, setStale] = useState(false);
  const [paused, setPaused] = useState(false);
  // The ONE announced region's content. Written on user-initiated outcomes and
  // on the called transition, and never by a poll tick.
  const [cue, setCue] = useState("");

  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const backoffRef = useRef(POLL_INTERVAL_MS);
  // One monotonic generation. A load applies its result only if the generation
  // it was issued under is unchanged; resume and the visibility return bump it.
  const generationRef = useRef(0);
  const runningRef = useRef(true);
  // The timer always calls the LATEST tick, so the loop reads current state
  // without a ref mirror of every field it needs.
  const tickRef = useRef<() => void>(() => undefined);
  // Whether anything has ever loaded. A failure with data on screen degrades to
  // stale-and-labelled; a failure with nothing on screen has to say so.
  const loadedRef = useRef(false);
  // The called announcement is guarded on the PREVIOUS value, so it fires on the
  // edge rather than on every tick that observes the same fact.
  const calledRef = useRef(false);

  const clearTick = () => {
    if (timerRef.current !== null) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
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

  const stop = () => {
    runningRef.current = false;
    clearTick();
  };

  const load = async () => {
    const generation = generationRef.current;
    try {
      const ticket = await api.getQueuePosition(ticketId);
      if (generation !== generationRef.current) {
        return;
      }
      loadedRef.current = true;
      setView({ kind: "live", ticket });
      // The freshness claim changes ONLY on a success, which is what makes it a
      // claim the page can keep.
      setUpdatedAt(new Date().toISOString());
      setStale(false);
      backoffRef.current = POLL_INTERVAL_MS;
      if (CLOSED_STATUSES.has(ticket.status)) {
        clearCheckinTicket();
        stop();
        return;
      }
      if (ticket.called_at !== null && !calledRef.current) {
        calledRef.current = true;
        // The one thing this page exists to tell her, and she may not be looking
        // at the screen. A user-relevant event, not a poll artefact.
        setCue(t("checkin.called"));
      }
    } catch (error: unknown) {
      if (generation !== generationRef.current) {
        return;
      }
      // The terminal predicate is {404, 400 VALIDATION_ERROR} — NOT the board's
      // {401, 403}. The storefront carries no session, so both of those are
      // unreachable here and copying them would ship a dead branch while missing
      // the live ones.
      if (isNotFound(error)) {
        clearCheckinTicket();
        stop();
        setView({ kind: "notFound" });
        return;
      }
      // Stale-and-labelled beats empty: blanking a correct position to report a
      // network fault throws away the only thing she came here to read.
      if (loadedRef.current) {
        setStale(true);
      } else {
        setView({ kind: "failed" });
      }
      backoffRef.current = Math.min(backoffRef.current * 2, MAX_BACKOFF_MS);
    } finally {
      // Compared HERE too, not only in the two branches above: without it a
      // superseded load arms a second timer and the at-most-one property is
      // gone. schedule() no-ops once the loop is stopped, so both terminals and
      // the pause fall out of the same guard.
      if (generation === generationRef.current) {
        schedule(backoffRef.current);
      }
    }
  };

  const tick = () => {
    if (!runningRef.current || document.hidden) {
      return;
    }
    void load();
  };

  // No dependency array: the timer must always call the latest closure.
  useEffect(() => {
    tickRef.current = tick;
  });

  useEffect(() => {
    // ⚠ FIRST, and it is what makes this effect IDEMPOTENT. The cleanup below
    // sets runningRef false and nothing else ever sets it true except resume(),
    // so without this line a setup -> cleanup -> setup cycle leaves the loop
    // permanently dead while the UI still shows a pause control. React requires
    // effects to survive that cycle and StrictMode performs exactly it.
    runningRef.current = true;
    void load();
    return () => {
      // ⚠ THE UNMOUNT FIX, and clearTick() alone does not do it. clearTick()
      // cancels the timer armed RIGHT NOW; the arming site is a .finally(),
      // which runs AFTER this cleanup when a request is in flight, and nothing
      // in tick -> load -> finally -> schedule touches React state — so the loop
      // would outlive the component forever. On this surface that is an
      // anonymous 5s loop against a public endpoint from a phone in a bag, one
      // per navigation away, for the rest of the session.
      runningRef.current = false;
      clearTick();
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
      // by however long it was hidden, and five more seconds of a wrong number
      // is the worst moment to add.
      generationRef.current += 1;
      clearTick();
      tickRef.current();
    };
    document.addEventListener("visibilitychange", onVisibility);
    return () => {
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, []);

  const pause = () => {
    runningRef.current = false;
    clearTick();
    setPaused(true);
    setCue(t("checkin.pausedCue"));
  };

  const resume = () => {
    runningRef.current = true;
    setPaused(false);
    // A resume is a fresh user intent, not a continuation of a backed-off retry:
    // a control that inherited a sixty-second gap would look like a control that
    // did not work.
    backoffRef.current = POLL_INTERVAL_MS;
    generationRef.current += 1;
    clearTick();
    setCue(t("checkin.resumedCue"));
    tickRef.current();
  };

  const retry = () => {
    generationRef.current += 1;
    clearTick();
    tickRef.current();
  };

  const ticket = view.kind === "live" ? view.ticket : null;
  const closed = ticket !== null && CLOSED_STATUSES.has(ticket.status);
  // ⚠ F58 MAKES `called_at` AND `in_service` CO-OCCUR FOR THE FIRST TIME. A
  // dispatch moves the ticket to `in_service` and deliberately leaves the call
  // timestamp standing — it is the record that she was summoned, and the one
  // column the wall board reads — so the two facts are now true together of a
  // woman standing in a fitting room. The arms are ordered closed → inService →
  // called → position: without that, the `called` arm wins and this page tells
  // her to approach the counter, while «התור שלך התחיל» is unreachable on the
  // only path in the product that produces it.
  //
  // *Declined the alternative* — having take-next clear `called_at` — because it
  // would erase the record that she was summoned, on the one column F59 reads,
  // for a rendering problem that belongs to the renderer.
  const inService = ticket !== null && ticket.status === "in_service";
  const called = ticket !== null && ticket.called_at !== null;
  const live = ticket !== null && !closed;

  const freshTime = updatedAt === null ? "" : TIME.format(new Date(updatedAt));
  // Precedence in the one slot: paused beats stale, because a stopped loop
  // cannot fail a tick — the stop is the cause in force and the resume control
  // is the remedy. Three distinguishable SENTENCES rather than one sentence and
  // a colour, which is the defect this rule exists to catch.
  const freshKey = paused ? "checkin.pausedAt" : stale ? "checkin.staleAt" : "checkin.updatedAt";

  return (
    <div data-testid="queue-position" className={pageClass}>
      <Heading>{t("checkin.positionLabel")}</Heading>

      {view.kind === "loading" && (
        <>
          <VisuallyHidden>
            <span role="status">{t("checkin.positionLoading")}</span>
          </VisuallyHidden>
          <Skeleton variant="text" lines={3} />
        </>
      )}

      {/* BEFORE the auto-updating number in the DOM, and the pause control is the
          first control in the section. A 2.2.2 mechanism placed after the
          content it governs is reachable only by walking content that repaints
          under the walk. Absent once the loop has reached a terminal: offering a
          pause for a loop that can never run again is a lie about the page. */}
      {live && (
        <div className="flex flex-wrap items-center gap-3 text-sm text-ink-muted">
          <span
            data-testid="queue-freshness"
            // Visible, in the reading order and NEVER aria-hidden: this is the
            // page's only honesty signal, and hiding it would mean a screen
            // reader user could not learn the number stopped updating twenty
            // minutes ago. It is also outside every announced region — a
            // role="status" rewritten every five seconds passes every automated
            // check and is unusable.
            className={cn(paused || stale ? "font-semibold text-warning-text" : undefined)}
          >
            {t(freshKey)} <bdi dir="ltr">{freshTime}</bdi>
          </span>
          <Button
            variant="ghost"
            size="md"
            onClick={paused ? resume : pause}
          >
            {t(paused ? "checkin.resume" : "checkin.pause")}
          </Button>
        </div>
      )}

      {ticket !== null && closed && (
        <p className="max-w-[60ch] text-base text-ink">{t("checkin.closed")}</p>
      )}

      {ticket !== null && !closed && inService && (
        <p className="font-display text-3xl text-ink">{t("checkin.statusInService")}</p>
      )}

      {ticket !== null && !closed && !inService && called && (
        <p data-testid="queue-called" className="font-display text-3xl text-ink">
          {t("checkin.called")}
        </p>
      )}

      {ticket !== null && !closed && !inService && !called && ticket.position !== null && (
        <div className="flex flex-col gap-2">
          <p data-testid="queue-number" className="font-display text-6xl text-ink">
            <bdi dir="ltr">{ticket.position}</bdi>
          </p>
          <p className="text-base text-ink-muted">{t("checkin.statusWaiting")}</p>
        </div>
      )}

      {view.kind === "notFound" && (
        <>
          <p role="alert" className="max-w-[60ch] text-base text-ink">
            {t("checkin.notFound")}
          </p>
          <p className="max-w-[60ch] text-base text-ink-muted">{t("checkin.notFoundHint")}</p>
        </>
      )}

      {view.kind === "failed" && (
        <>
          <p role="alert" className="max-w-[60ch] text-base text-ink-muted">
            {t("checkin.loadFailed")}
          </p>
          <div className="flex">
            <Button variant="secondary" size="md" fullWidthMobile onClick={retry}>
              {t("checkin.retry")}
            </Button>
          </div>
        </>
      )}

      {(view.kind === "notFound" || closed) && (
        <div className="flex">
          <ButtonLink href="/checkin" variant="secondary" size="md" fullWidthMobile>
            {t("checkin.backToCheckin")}
          </ButtonLink>
        </div>
      )}

      {/* The ONE announced region, and the poll may NEVER write into it — not
          even a tick whose value is unchanged. Everything it carries is either a
          user-initiated outcome or the one event she came here for. */}
      <VisuallyHidden>
        <span role="status" data-testid="queue-cue">
          {cue}
        </span>
      </VisuallyHidden>
    </div>
  );
}
