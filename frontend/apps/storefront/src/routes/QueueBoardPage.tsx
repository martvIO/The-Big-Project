import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Button, JERusalem, Skeleton, VisuallyHidden, cn } from "@boutique/ui";
import { api } from "../api";
import type { QueueBoardView } from "../api";

// The public wall board: /queue, opened once in a kiosk browser and left on a
// television across a boutique floor.
//
// This is the most privacy-sensitive surface in the product. It is anonymous and
// unauthenticated — anyone who knows the boutique's address can open it — so the
// payload carries three fields per row and no ticket id, and every extra field
// on the wire would be a disclosure to strangers. What the page renders is what
// the server chose to publish; it derives nothing about anybody.
//
// ⚠ NOTHING IS EVER HIGHLIGHTED YET. called_at has no writer until F58, so
// `called` is false on every entry, always, and the board only grows until the
// midnight queue-day roll. The board is not deployable to a customer-facing wall
// in that interim — it exists so the code is reviewed, tested and merged.
//
// The container is NOT the position page's: its pb-16 is the fixed accessibility
// trigger's own footprint, and StorefrontLayout's footer already reserves
// --space-a11y-footprint for it. A second reservation double-counts 68px, and on
// a screen whose whole layout question is "how many rows fit above the fold",
// 68px is most of a row.
const pageClass = "mx-auto flex w-full max-w-[1400px] flex-col gap-6 px-4 pt-6 pb-6 md:px-8";

// One client constant, the position page's. If the pilot says five seconds is
// too expensive, halving the load is this line and the UI does not change.
const POLL_INTERVAL_MS = 5_000;
// The cap, doubling from the base. There is a server-side per-boutique ceiling
// too, sized for the wall plus a room of phones, but the client backoff is what
// keeps a sick server from being hammered by every screen in every shop at once.
const MAX_BACKOFF_MS = 60_000;

// ⚠ THERE IS NO TERMINAL SET HERE, and its absence is the deliberate divergence
// from QueuePositionPage.tsx, which a builder will have open beside this file.
// That page stops on a closed status and on a 404 because HER ticket is gone and
// no retry brings it back. This page has no ticket, no capability and NOBODY AT
// THE KEYBOARD: a 404 means TENANT_NOT_FOUND — a fact about the server, not a
// dead link the reader holds — and an unattended screen that gives up
// permanently needs a human to notice and reload. There is none. So every
// failure backs off to the 60s cap and keeps trying until the server heals
// itself.
//
// The ONE exception is document.hidden, which stops rather than slows the loop
// and whose only way back is the visibilitychange listener. On a kiosk reporting
// hidden while the panel is lit that freezes indefinitely — accepted as a
// ceiling rather than fixed, because removing the guard would poll a genuinely
// hidden tab forever. The mitigation is configuration: a single full-screen tab
// with screen blanking disabled.

// Multi-line on purpose: qa-greps.sh flags a single-line Intl.DateTimeFormat
// without a timeZone, and a formatter built without one reads the DEVICE clock —
// on a television nobody has ever set the clock on. The freshness claim is about
// the boutique's clock.
const TIME = new Intl.DateTimeFormat("en-GB", {
  timeZone: JERusalem,
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
});

// SC 1.4.4. The preferred term is `rem + vh` and NEVER vh alone: with a vh-only
// preferred value the accessibility menu's text-size boost is a complete no-op
// on every element of this page, at 1080p, at 4K and on a phone — and browser
// zoom does not rescue it either, because page zoom shrinks the CSS-pixel
// viewport and enlarges the pixel, so vh text is net-constant by construction.
// The vh half tracks the panel; the rem half tracks the user. Axe has no rule
// for any of it, so a class assertion is the only guard.
const POSITION_SCALE = "text-[clamp(2.5rem,2.5rem+3.3vh,9rem)]";
const NAME_SCALE = "text-[clamp(2rem,2rem+2.5vh,7rem)]";
const HEADING_SCALE = "text-[clamp(1.5rem,1.5rem+1.8vh,4rem)]";
// Deliberately the smallest text on a screen designed to be read from four
// metres. A control the room can read is a control the room will eventually
// press, and a wall frozen by a passer-by reads as LIVE to the next woman who
// sits down. Every user this control is for — the kiosk operator, any woman who
// opens the same public URL on her own phone, any keyboard user — is within arm's
// reach of a pointer.
const CONTROL_SCALE = "text-[clamp(1rem,1rem+0.8vh,2rem)]";

type View =
  | { kind: "loading" }
  | { kind: "board"; board: QueueBoardView }
  // The FIRST request failed and nothing ever loaded. Recoverable, so it offers
  // a retry — for the phone user, who is the only one who will ever press it.
  // The loop is still running underneath, so the wall heals itself.
  | { kind: "failed" };

export function QueueBoardPage() {
  const { t } = useTranslation();

  const [view, setView] = useState<View>({ kind: "loading" });
  const [updatedAt, setUpdatedAt] = useState<string | null>(null);
  const [stale, setStale] = useState(false);
  const [paused, setPaused] = useState(false);
  // The ONE announced region's content. User-initiated outcomes only — and
  // unlike the position page, no content transition ever reaches it.
  const [cue, setCue] = useState("");

  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const backoffRef = useRef(POLL_INTERVAL_MS);
  // One monotonic generation. A load applies its result only if the generation
  // it was issued under is unchanged; resume, retry and the visibility return
  // bump it.
  const generationRef = useRef(0);
  const runningRef = useRef(true);
  // The timer always calls the LATEST tick, so the loop reads current state
  // without a ref mirror of every field it needs.
  const tickRef = useRef<() => void>(() => undefined);
  // Whether anything has ever loaded. A failure with a board on screen degrades
  // to stale-and-labelled; a failure with nothing on screen has to say so.
  const loadedRef = useRef(false);

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
    if (!runningRef.current || document.hidden) {
      return;
    }
    timerRef.current = setTimeout(() => {
      timerRef.current = null;
      tickRef.current();
    }, ms);
  };

  const load = async () => {
    const generation = generationRef.current;
    try {
      const board = await api.getQueueBoard();
      if (generation !== generationRef.current) {
        return;
      }
      loadedRef.current = true;
      setView({ kind: "board", board });
      // The freshness claim changes ONLY on a success, which is what makes it a
      // claim the page can keep.
      setUpdatedAt(new Date().toISOString());
      setStale(false);
      backoffRef.current = POLL_INTERVAL_MS;
    } catch {
      if (generation !== generationRef.current) {
        return;
      }
      // NO isNotFound branch, NO status branch, no terminal of any kind — see
      // the block above. Stale-and-labelled beats empty: blanking a correct
      // board because one request failed throws away the only thing the room
      // came to read, and a flooder who can make the wall stale must not be able
      // to make it wrong.
      if (loadedRef.current) {
        setStale(true);
      } else {
        setView({ kind: "failed" });
      }
      backoffRef.current = Math.min(backoffRef.current * 2, MAX_BACKOFF_MS);
    } finally {
      // Compared HERE too, not only in the two branches above: without it a
      // superseded load arms a second timer and the at-most-one property is
      // gone. schedule() no-ops once the loop is stopped, so the pause falls out
      // of the same guard.
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
    // permanently dead while the UI still shows a working-looking pause control.
    // React requires effects to survive that cycle and StrictMode performs
    // exactly it.
    //
    // On a wall the symptom is a television showing a CORRECT board frozen at
    // the moment of mount, with nobody in the room to notice — the worst
    // instance of this bug in the product.
    runningRef.current = true;
    void load();
    return () => {
      // ⚠ THE UNMOUNT FIX, and clearTick() alone does not do it. clearTick()
      // cancels the timer armed RIGHT NOW; the arming site is a .finally(),
      // which runs AFTER this cleanup when a request is in flight, and nothing
      // in tick -> load -> finally -> schedule touches React state — so the loop
      // would outlive the component forever. This has shipped as a defect twice
      // in this repo.
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
      // by however long it was hidden, and on a wall that gap is invisible to
      // everyone reading it.
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

  const board = view.kind === "board" ? view.board : null;
  const hidden = board !== null ? board.waiting_total - board.entries.length : 0;

  const freshTime = updatedAt === null ? "" : TIME.format(new Date(updatedAt));
  // Precedence in the one slot: paused beats stale, because a stopped loop
  // cannot fail a tick — the stop is the cause in force and the resume control
  // is the remedy. Three distinguishable SENTENCES rather than one sentence and
  // a colour, which is the defect this rule exists to catch.
  const freshKey = paused ? "checkin.pausedAt" : stale ? "checkin.staleAt" : "checkin.updatedAt";

  return (
    <div data-testid="queue-board" className={pageClass}>
      <div className="flex flex-col gap-3">
        <h1 className={cn("font-display text-ink", HEADING_SCALE)}>{t("queueBoard.heading")}</h1>
        {/* The gold hairline every non-catalog route carries, grown from
            h-px w-12: at 0.634 mm per CSS pixel a 1px rule is 0.63mm and is not
            seen from a seat. */}
        <span aria-hidden="true" className="h-1 w-32 bg-gold" />
      </div>

      {view.kind === "loading" && (
        <>
          <VisuallyHidden>
            <span role="status" data-testid="queue-board-loading-status">
              {t("queueBoard.loading")}
            </span>
          </VisuallyHidden>
          {/* ONE block skeleton, not variant="text": h-4 bars on a screen whose
              rows are 115px tall are wrong twice over, and that variant's three
              pulses would be the page's entire motion budget spent at boot. */}
          <div className="flex-1">
            <Skeleton variant="block" />
          </div>
        </>
      )}

      {/* BEFORE the auto-updating content in the DOM, and the pause is the first
          control in the section: a 2.2.2 mechanism placed after the content it
          governs is reachable only by walking content that repaints under the
          walk. Rendered in the live, empty AND error states — the copied
          `live &&` gate does NOT come across, because this loop has no terminal
          and a request is still going out every 5-60s in the error arm.
          Withheld only before the first response, where a pause would be a lie
          about a page that is not updating anything yet. */}
      {view.kind !== "loading" && (
        <div className="flex flex-wrap items-center gap-6">
          <span
            data-testid="queue-board-freshness"
            // Visible, in the reading order and NEVER aria-hidden: this is the
            // page's only honesty signal, and it is what resolves the whole
            // 2.2.2 wall-screen tension — a pause the ROOM could reach would be
            // actively harmful, so the protection against a frozen wall is that
            // even the frozen state is labelled, on the wall, in Hebrew. It is
            // also outside every announced region: a role="status" rewritten
            // every five seconds passes every automated check and is unusable.
            //
            // text-ink and NOT the shipped text-warning-text escalation: on a
            // panel that swap drops this line from 15.24:1 to 5.70:1 at the
            // exact moment it matters most. font-semibold stays; the state is
            // carried by three distinguishable sentences.
            className={cn("text-ink", NAME_SCALE, (paused || stale) && "font-semibold")}
          >
            {t(freshKey)} <bdi dir="ltr">{freshTime}</bdi>
          </span>
          {/* The clamp goes on a DESCENDANT and never on the Button: sizes.md
              bakes text-base into the component and cn() is a plain join with no
              tailwind-merge, so a className here would ship both utilities and
              let Tailwind's stylesheet order decide the rendered size. */}
          <Button variant="ghost" size="md" onClick={paused ? resume : pause}>
            <span className={CONTROL_SCALE}>{t(paused ? "checkin.resume" : "checkin.pause")}</span>
          </Button>
        </div>
      )}

      {/* No Card and no divide-y: a frame spends 48px of vertical budget on
          something nobody sees at four metres, and a divider is a hairline at
          0.63mm. Whitespace is the separator. */}
      {board !== null && board.entries.length > 0 && (
        <ul className="flex flex-col gap-2">
          {board.entries.map((row) => (
            // Keyed by POSITION, never by name: a name key collides on two
            // different women called נועה AND on one woman holding two tickets,
            // which under Ruling 3 is an ordinary outcome rather than an edge
            // case. Rows hold no input state and no focus, so a repaint swaps
            // text inside a stable element.
            <li
              key={row.position}
              data-testid="queue-board-row"
              // items-baseline, not items-center: a 75.6px number and a 59.0px
              // name centred against each other float apart. flex-wrap is for
              // the phone and never fires on a panel.
              className={cn(
                "flex flex-wrap items-baseline gap-6 py-2",
                row.called && "border-s-8 border-gold-strong bg-surface ps-4",
              )}
            >
              <bdi
                dir="ltr"
                // A fixed gutter that keeps the name column on one axis, plus
                // headroom against a future row-cap change. Not about two-digit
                // numbers: at a cap of five the position is always one digit.
                className={cn(
                  "w-[2ch] shrink-0 text-center font-display tabular-nums text-ink",
                  POSITION_SCALE,
                )}
              >
                {row.position}
              </bdi>
              {/* Bare <bdi>, no dir: dir="ltr" on a Hebrew name is itself a bidi
                  defect and the worse one, because it looks deliberate. */}
              <bdi
                className={cn(
                  "min-w-0 font-display text-ink [overflow-wrap:anywhere]",
                  NAME_SCALE,
                )}
              >
                {row.first_name}
              </bdi>
              {/* THE WORD is what keeps the highlight out of SC 1.4.1 — a
                  background alone is invisible to a woman with a colour-vision
                  difference sitting four metres away, which is the entire
                  audience. The number and the name stay text-ink. */}
              {row.called && (
                <span className={cn("text-warning-text", NAME_SCALE)}>
                  {t("queueBoard.called")}
                </span>
              )}
            </li>
          ))}
        </ul>
      )}

      {/* The state the screen is in for most of the day, and it is designed. Not
          EmptyState: its title is text-xl, which is a caption on a wall. */}
      {board !== null && board.entries.length === 0 && (
        <div data-testid="queue-board-empty" className="flex flex-col gap-3">
          <p className={cn("text-center font-display text-ink", POSITION_SCALE)}>
            {t("queueBoard.empty")}
          </p>
          <p className={cn("text-center text-ink", NAME_SCALE)}>{t("queueBoard.emptyHint")}</p>
        </div>
      )}

      {/* One static line, never motion. A scrolling list, an auto-paginating
          carousel and a "page 1 of 8" rotation were all declined: every one is
          content that moves on its own, and a woman trying to find her number on
          a list that pages away under her eyes is worse off than one who reads
          «ועוד 35 בתור». The count is COMPUTED, never echoed. */}
      {board !== null && hidden > 0 && (
        <p
          data-testid="queue-board-overflow"
          className={cn("text-ink", NAME_SCALE)}
        >
          {t("queueBoard.overflow", { count: hidden })}
        </p>
      )}

      {view.kind === "failed" && (
        <>
          {/* At the name scale, because the room must be able to tell a broken
              board from an empty one: a blank screen reads as «אין ממתינות» and
              a woman acts on it. */}
          <p role="alert" className={cn("text-ink", NAME_SCALE)}>
            {t("queueBoard.loadFailed")}
          </p>
          <div className="flex">
            <Button variant="secondary" size="md" onClick={retry}>
              <span className={CONTROL_SCALE}>{t("checkin.retry")}</span>
            </Button>
          </div>
        </>
      )}

      {/* The ONE announced region, and the poll may NEVER write into it — not
          even a tick whose value is unchanged. It carries the pause and resume
          cues and nothing else: this board is about OTHER PEOPLE, and pushing a
          call-forward into a stranger's screen reader is both noise and a
          broadcast she did not agree to. Deliberately unlike the position page,
          which announces the one event its own holder came for. */}
      <VisuallyHidden>
        <span role="status" data-testid="queue-board-cue">
          {cue}
        </span>
      </VisuallyHidden>
    </div>
  );
}
