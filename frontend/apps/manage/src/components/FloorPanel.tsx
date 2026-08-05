import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Badge, Button, Card, EmptyState, Skeleton } from "@boutique/ui";
import type { BadgeVariant } from "@boutique/ui";
import { api, ApiError } from "../api";
import type { DispatchResult, Room, StaffCard, StaffCardStatus, Waitlist } from "../api";
import { isolateBidi, isolateLtr } from "../lib/booking";
import { elapsedLine } from "../lib/elapsed";
import { jerusalemTime } from "../lib/jerusalem";
import { roleLabelKey } from "../lib/roles";
import { IDLE_STOP_MINUTES, usePoll } from "../lib/usePoll";
import type { TickOutcome } from "../lib/usePoll";
import { RoomsPanel } from "./RoomsPanel";
import { SosCentre } from "./SosCentre";
import { SosRaiseDialog } from "./SosRaiseDialog";
import { WaitlistPanel } from "./WaitlistPanel";

// F57. The floor's staff cards: a name, a role and a live status, plus the break
// toggle the status is derived from.
//
// **All of this panel's state lives HERE and nothing above it.** BoardSection is
// a SIBLING, not a parent, which is what makes a floor tick repaint the cards
// and nothing else. Lifting the rows into BoardSection or App would make every
// floor tick repaint the day's booking list — a rule the plan may not relax
// (spec D11).
//
// It owns its OWN usePoll instance, so the board screen carries two loops and
// two pause controls for the two roles that see both. That is the answer rather
// than a problem: one control governing both loops means lifting pause state
// into a shared parent, the exact coupling D11 forbids. What it costs is
// distinguishable accessible names, which board.pauseAria and floor.pauseAria
// provide and a test asserts.

interface FloorPanelProps {
  /** The signed-in staffer's id — for the «זו את» marker and the self-toggle. */
  selfId: string;
  /** Her role. Cosmetics only: the control is the server's D6 check. */
  role: string;
}

const ELEVATED = new Set(["owner", "shift_manager"]);

// The WORD carries the state; the colour never does. THREE-WAY since F36: it
// replaced a binary ternary that fell to its else branch on `occupied` and
// printed «פנויה» about a staffer standing in room 2.
//
// ⚠ A `Record<StaffCardStatus, …>` on purpose, with NO fallback: a fourth
// status is a COMPILE error here rather than a wrong word that ships silently —
// the argument lib/roles.ts makes for ROLE_LABEL_KEY, and the reason the binary
// ternary was a latent bug rather than a safety net. The wire cannot carry a
// value outside the union: the backend asserts the three literals set-equal.
const STATUS_BADGE: Record<StaffCardStatus, { variant: BadgeVariant; labelKey: string }> = {
  available: { variant: "success", labelKey: "floor.statusAvailable" },
  break: { variant: "warning", labelKey: "floor.statusBreak" },
  occupied: { variant: "neutral", labelKey: "floor.statusOccupied" },
};

// Whether the focused element sits inside a card that the incoming list drops.
// BoardSection's `holdsFocus` shape, asking the question one card at a time.
function departingCardHoldsFocus(incoming: readonly StaffCard[]): boolean {
  const active = document.activeElement;
  if (!(active instanceof Element)) {
    return false;
  }
  const held = active.closest("[data-staff-id]")?.getAttribute("data-staff-id");
  if (held === undefined || held === null) {
    return false;
  }
  return !incoming.some((card) => card.id === held);
}

export function FloorPanel({ selfId, role }: FloorPanelProps) {
  const { t } = useTranslation();

  const [cards, setCards] = useState<StaffCard[] | null>(null);
  // F36's half of the same payload. It lives HERE and not in RoomsPanel for the
  // same reason the cards do not live in BoardSection: the rooms and the staff
  // arrive in one response, so two owners would be two freshness claims that can
  // disagree by an interval with no way to tell which to believe.
  const [rooms, setRooms] = useState<Room[] | null>(null);
  // F58's third of the same payload, here for the same reason: one response,
  // one owner, one freshness claim. Two owners would be two claims that can
  // disagree by an interval with no way to tell which to believe — and the
  // whole argument for putting the waitlist on this envelope rather than behind
  // a second poll is that «עודכן 14:07» stays true of the staff, the rooms AND
  // the queue simultaneously.
  const [waitlist, setWaitlist] = useState<Waitlist | null>(null);
  // How many ticks have SUCCEEDED. RoomsPanel's tile alert promises «הרשימה
  // תתוקן בעדכון הבא» and a child cannot clear it imperatively from inside
  // `load` the way the card alert below is cleared — so the fact that an update
  // happened travels as its own monotonic signal rather than being inferred from
  // the payload, which a byte-equal answer would not carry.
  const [fetchCount, setFetchCount] = useState(0);
  const [updatedAt, setUpdatedAt] = useState<string | null>(null);
  // The SERVER's instant at serialisation, from the payload. Elapsed minutes are
  // computed against it and it only moves on a successful poll, which is what
  // freezes «כבר 42 דק'» exactly when the panel freezes.
  const [serverNow, setServerNow] = useState<string | null>(null);
  const [stale, setStale] = useState(false);
  const [loadFailed, setLoadFailed] = useState(false);
  // The cue carries its interpolated NAME alongside its text, because the name
  // has to render inside a bare <bdi> and a flat string cannot say where it
  // starts. `name: null` is every cue that interpolates no person.
  //
  // ⚠ AND A NONCE, which is what makes a REPEATED cue audible. React skips the
  // `nodeValue` write when a text child re-renders to the same string, so a
  // second «הקריאה נרשמה.» for the next woman in the queue — the cue that
  // interpolates nothing at all — mutated NOTHING inside role="status" and
  // announced nothing. Same for a second skip and a second removal. The nonce
  // keys the span below, so every write replaces that node and the region always
  // sees a childList mutation. One guard on the writer covers all nine call
  // sites, four of them in child panels through `onCue`; a per-cue workaround
  // would have to be remembered by whoever adds the tenth.
  //
  // `useCallback` with no deps because `onCue` is a DEPENDENCY of SosCentre's
  // pending-cue effect (SosCentre.tsx:269) — this used to be React's own stable
  // `setCue`, and handing that effect a fresh identity on every render would be
  // a behaviour change smuggled in beside an accessibility fix.
  const [cue, writeCue] = useState<{ text: string; name: string | null; nonce: number }>({
    text: "",
    name: null,
    nonce: 0,
  });
  const setCue = useCallback(
    (next: { text: string; name: string | null }) =>
      writeCue((current) => ({ ...next, nonce: current.nonce + 1 })),
    [],
  );
  const [busyIds, setBusyIds] = useState<readonly string[]>([]);
  const [cardError, setCardError] = useState<{ id: string; text: string } | null>(null);

  const headingRef = useRef<HTMLHeadingElement>(null);
  const cueRef = useRef<HTMLParagraphElement>(null);
  const cardAlertRef = useRef<HTMLParagraphElement>(null);
  const controlRefs = useRef(new Map<string, HTMLButtonElement | null>());
  const restoreFocusRef = useRef<string | null>(null);
  const cardsRef = useRef<StaffCard[] | null>(null);
  const focusHeadingRef = useRef(false);
  // Set when a SUCCESSFUL POLL is about to unmount the focused in-card alert.
  // Distinct from restoreFocusRef, which the [busyIds] effect owns and which
  // does not fire here — the toggle finished long ago.
  const reclaimFocusRef = useRef<string | null>(null);
  // `load` runs outside render and closes over a stale `cardError`, so the id it
  // needs is mirrored here.
  const cardErrorRef = useRef<{ id: string; text: string } | null>(null);
  // ⚠ THE RAISE DIALOG'S TRIGGER, HELD HERE AND NOT IN RoomsPanel. RoomsPanel's
  // own MOVE-4 effect is keyed on ITS `openDialog` state, which never changes
  // for a dialog this panel owns — so the effect would never run, the native
  // <dialog>'s own return would have no target, and focus would drop to <body>
  // for something the user did. The trigger element travels UP instead.
  const sosTriggerRef = useRef<HTMLButtonElement | null>(null);
  // The dialog's open state lives HERE because this panel is the common parent
  // of both triggers — the SOS centre's and the room tile's.
  const [raiseOpen, setRaiseOpen] = useState(false);
  const [raiseAssignmentId, setRaiseAssignmentId] = useState<string | null>(null);
  const mutationsRef = useRef(0);
  // The pointer hold is the CALLER's — usePoll deliberately does not supply it
  // (D10), and this panel needs its own because the since-line renders only on a
  // break: a remote break starting on card 2 grows it ~20px and slides every
  // control below it, and at 375 the control is on its own line, i.e. exactly
  // the thing that moves.
  //
  // ⚠ F36 makes the same mechanism carry far more than ~20px. A remote claim
  // adds an occupancy line to a staff card, and a room being claimed grows its
  // tile by a holder line, a role line, a client line, an elapsed line, a dress
  // list and two more controls — directly above the tile a finger is already
  // travelling toward.
  //
  // ⚠ F58 makes it worse in a NEW WAY, and the mechanism is unchanged. A remote
  // skip does not grow a row: it MOVES one, from position 1 to position 12, so
  // every row between them shifts up by a whole row — directly under a finger
  // travelling toward «הסרה», the one irreversible control in this feature, on
  // the row below.
  //
  // ⚠ F37 adds one more case and NO code: an SOS-centre row appearing ABOVE the
  // rooms panel moves every tile below it, directly under a travelling finger —
  // and that row arrives from a loop this hold does not govern, so the hold
  // covers the repaint it can and the emergency arrives regardless.
  const holdRef = useRef(false);
  const tickRef = useRef<() => TickOutcome>(() => {});

  const poll = usePoll({
    run: () => tickRef.current(),
    onIdleStop: () =>
      setCue({ text: t("floor.idleStopped", { minutes: IDLE_STOP_MINUTES }), name: null }),
  });
  const { mode, terminal } = poll;

  const load = async () => {
    const generation = poll.generation();
    try {
      const result = await api.getFloor();
      if (!poll.isCurrent(generation)) {
        return;
      }
      // Decided BEFORE the new list is applied — the only moment both lists
      // exist. A card can only leave by being deactivated.
      focusHeadingRef.current = departingCardHoldsFocus(result.staff);
      cardsRef.current = result.staff;
      setCards(result.staff);
      setRooms(result.rooms);
      setWaitlist(result.waitlist);
      setFetchCount((count) => count + 1);
      setServerNow(result.server_now);
      // The freshness claim changes ONLY on a success, which is what makes it a
      // claim the panel can keep.
      setUpdatedAt(new Date().toISOString());
      setStale(false);
      setLoadFailed(false);
      // ⚠ The alert we are about to remove may be HOLDING FOCUS: the failure
      // effect below moves focus into it, and this clear runs on the very next
      // successful tick — about five seconds later, with no user action at all.
      // Removing a focused node drops document.activeElement to <body>, so her
      // next Tab restarts at the skip link.
      //
      // The departing-card rescue cannot cover this one: the card is still in
      // the incoming list (a 5xx or a dropped request leaves the colleague
      // live), so `departingCardHoldsFocus` is false. Hand focus back to that
      // card's own control — where she was when she tapped — and fall back to
      // the heading if the control is gone.
      if (cardAlertRef.current !== null && document.activeElement === cardAlertRef.current) {
        reclaimFocusRef.current = cardErrorRef.current?.id ?? null;
      }
      // The in-card alert promises «הרשימה תתוקן בעדכון הבא» and this is the
      // update that keeps it.
      setCardError(null);
      poll.succeeded();
    } catch (error) {
      if (!poll.isCurrent(generation)) {
        return;
      }
      if (poll.fail(error)) {
        return;
      }
      // Stale-and-labelled beats empty: blanking to the outage message would
      // throw away correct data to report a network fault.
      if (cardsRef.current === null) {
        setLoadFailed(true);
      } else {
        setStale(true);
      }
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
    if (holdRef.current) {
      holdRef.current = false;
      return "held";
    }
    void load();
  };

  // Assigned during render, not in an effect: usePoll's mount effect runs before
  // any effect in this component, so an effect-assigned ref would still hold its
  // placeholder when the hook fires the FIRST load.
  tickRef.current = tick;
  // Mirrored during render for the same reason tickRef is: `load` runs outside
  // render and would otherwise close over a stale `cardError`.
  cardErrorRef.current = cardError;

  useEffect(() => {
    // A pointerdown holds the NEXT repaint and is consumed by it. Consumed
    // rather than latched, so a lost pointerup costs at most one interval and
    // can never stall the panel.
    const hold = () => {
      holdRef.current = true;
    };
    const release = () => {
      holdRef.current = false;
    };
    window.addEventListener("pointerdown", hold, { passive: true });
    window.addEventListener("pointerup", release, { passive: true });
    window.addEventListener("pointercancel", release, { passive: true });
    return () => {
      window.removeEventListener("pointerdown", hold);
      window.removeEventListener("pointerup", release);
      window.removeEventListener("pointercancel", release);
    };
  }, []);

  // ⚠ CORRECTED (F21 T11). This block used to claim that writing a
  // byte-identical string still mutates the text node, and that `setCue` with an
  // equal value is a React bail-out that guards against a spurious repeat. BOTH
  // ARE FALSE, and the second one had the danger backwards. `setCue` always
  // builds a fresh object, so it never bails out — and React, on re-render,
  // compares the text child and SKIPS the DOM write when the string is
  // unchanged, which is exactly the case that stayed SILENT. The nonce on the
  // cue state above is what fixes it.
  //
  // F34's F-7 remains true and is a DIFFERENT property: the poll may never write
  // here at all, and `the cue does NOT change across several consecutive ticks`
  // is the test that holds it. A single-tick assertion passes against the broken
  // version whenever the cue starts empty, so that test populates the cue first.

  useEffect(() => {
    // After a SUCCESSFUL toggle, focus returns to the tapped control. Unlike
    // F34's check-in it does NOT unmount — it renames «להפסקה» ⇄ «חזרה» — but
    // @boutique/ui's Button is disabled={disabled || loading}, so the browser
    // blurred it the instant the request started.
    //
    // Guarded on document.body so it can never steal focus from wherever she
    // moved it in the meantime (BoardSection.tsx's shipped shape).
    const pending = restoreFocusRef.current;
    if (pending === null || busyIds.includes(pending)) {
      return;
    }
    restoreFocusRef.current = null;
    if (document.activeElement === document.body) {
      controlRefs.current.get(pending)?.focus();
    }
  }, [busyIds]);

  useEffect(() => {
    // After a FAILED toggle, focus moves to the in-card alert. Keyed on the
    // error state rather than raised inside the handler, because the alert node
    // does not exist yet when setCardError runs. THE FAILURE PATH IS THE ONE
    // THAT GETS FORGOTTEN — it is how the same bug shipped twice in this repo
    // (F56 on the storefront, F34 on the board) with axe walking past it both
    // times, because axe cannot see a focus move that never happened.
    if (cardError !== null) {
      cardAlertRef.current?.focus();
      return;
    }
    // …and when it is CLEARED by a successful poll while it held focus, hand
    // focus back to that card's own control — where she was when she tapped.
    //
    // Keyed on `cardError` and NOT on `cards`, deliberately: a poll that returns
    // an unchanged list may hand `setCards` an identical reference, React bails
    // out of the update and a [cards] effect would never run. `cardError`
    // transitions non-null -> null on exactly this path, every time.
    const reclaim = reclaimFocusRef.current;
    reclaimFocusRef.current = null;
    if (reclaim === null || document.activeElement !== document.body) {
      return;
    }
    const control = controlRefs.current.get(reclaim);
    if (control !== undefined && control !== null) {
      control.focus();
      return;
    }
    headingRef.current?.focus();
  }, [cardError]);

  useEffect(() => {
    // A card that LEFT the list while holding focus hands focus to the panel
    // heading — F51's shipped pattern (StaffSection.tsx:80-92), no new string
    // and no stranded-card mechanism. Without it the browser drops focus to
    // <body> for something the user did not do.
    //
    // The flag is set in `load` BEFORE the new cards are applied, because that
    // is the only moment both lists exist; by the time this effect runs the
    // departing row is already gone from the DOM.
    if (!focusHeadingRef.current) {
      return;
    }
    focusHeadingRef.current = false;
    if (document.activeElement === document.body) {
      headingRef.current?.focus();
    }
  }, [cards]);

  // A room mutation's own response is the truth for its tile, and the freshness
  // stamp moves with it — the same contract `toggle` keeps for a card.
  //
  // ⚠ AN UPDATER, not a value, and this is the whole of review round 1's
  // MAJOR. The earlier shape took a finished list, so each caller rebuilt it
  // from the `rooms` PROP captured in the render that created its handler. The
  // loop issues no tick while a mutation is in flight — true, and the reason
  // the old comment here said no mirror was needed — but the collision is
  // MUTATION-vs-MUTATION, not tick-vs-mutation: `busy` is per room and `mutate`
  // counts rather than latches, so a claim on one tile and a release on another
  // overlap by design, and the second response to land rebuilt the list from a
  // base that predated the first. A claimed room rendered «פנוי» with a live
  // claim control, under a freshness stamp reset to now, until the next tick.
  const applyRooms = (update: (current: Room[]) => Room[]) => {
    setRooms((current) => update(current ?? []));
    setUpdatedAt(new Date().toISOString());
  };

  // Same contract, same reason — with one thing `applyRooms`'s does not buy:
  // every waitlist verb answers the WHOLE list, because a skip REORDERS it and
  // a remove SHORTENS it and a per-entry patch can express neither. So the
  // updater exists for the signature and the freshness stamp, and every call
  // site installs the server's list wholesale.
  const applyWaitlist = (update: (current: Waitlist) => Waitlist) => {
    setWaitlist((current) => update(current ?? { entries: [], truncated: false }));
    setUpdatedAt(new Date().toISOString());
  };

  // A dispatch is TWO halves of ONE act and they land in ONE paint: patching the
  // tile and waiting up to five seconds for the row to leave would render the
  // same woman as in-service and waiting. One freshness stamp, because it was
  // one response.
  const applyDispatch = (result: DispatchResult) => {
    setRooms((current) =>
      (current ?? []).map((item) => (item.id === result.room.id ? result.room : item)),
    );
    setWaitlist(result.waitlist);
    setUpdatedAt(new Date().toISOString());
  };

  useEffect(() => {
    // MOVE G — closing the dialog returns focus to the trigger that opened it,
    // falling back to this panel's own h2 when that trigger is gone.
    //
    // ⚠ THIS IS NOT A REUSE OF RoomsPanel's SHIPPED MOVE-4 EFFECT, and citing it
    // would ship the fifth focus bug in this repo. That effect is keyed on
    // ROOMS PANEL's OWN `openDialog` state, which never changes for a dialog
    // THIS component owns: it would never run, the native <dialog>'s own return
    // would have no target, and focus would drop to <body> for something the
    // user did. The tile passes its trigger ELEMENT up instead.
    if (raiseOpen) {
      return;
    }
    const trigger = sosTriggerRef.current;
    if (trigger === null) {
      return;
    }
    sosTriggerRef.current = null;
    if (document.activeElement !== document.body) {
      return;
    }
    if (trigger.isConnected) {
      trigger.focus();
      return;
    }
    headingRef.current?.focus();
  }, [raiseOpen]);

  const openRaise = (trigger: HTMLButtonElement, assignmentId: string | null) => {
    sosTriggerRef.current = trigger;
    setRaiseAssignmentId(assignmentId);
    setRaiseOpen(true);
  };

  const pause = () => {
    poll.pause();
    setCue({ text: t("floor.paused"), name: null });
  };

  const resume = () => {
    setCue({ text: t("floor.resumed"), name: null });
    poll.resume();
  };

  /**
   * The poll bookkeeping every mutation on this panel needs IDENTICALLY.
   *
   * Extracted from `toggle` in F36 rather than copied into the rooms panel: six
   * room actions would be six chances to drop the re-arm, which is the mistake
   * whose F34 form was "the loop survived unmount" and whose F57 form the
   * comment below names.
   *
   * ⚠ THE RE-ARM LIVES IN THE `.finally()`, not the success path: a REFUSED
   * action must not park the loop either, or the panel silently stops
   * converging the first time anybody acts.
   *
   * P-6 is handled here and nowhere else: a mutation answering 401 or 403 is
   * TERMINAL for the whole panel, on the same {401,403} rule the ticks use. The
   * alternative is an in-card alert plus a loop that keeps polling with a role
   * the server just refused — the panel disagreeing with itself for five
   * seconds and then doing the same thing anyway.
   *
   * Returns `null` when the call succeeded OR was terminal (both mean the
   * caller has nothing left to render), and the error otherwise: a break
   * toggle's 404 and a room claim's 404 are different Hebrew sentences, so
   * mapping one is the caller's job and never this helper's.
   */
  const mutate = async (run: () => Promise<void>): Promise<unknown> => {
    mutationsRef.current += 1;
    // The loop issues no tick while a mutation is in flight, so nothing can be
    // repainted underneath the request; the bump discards the one poll that
    // could still be in the air.
    poll.clearTick();
    poll.bump();
    try {
      await run();
      return null;
    } catch (error) {
      if (poll.fail(error)) {
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

  const toggle = async (card: StaffCard) => {
    // ⚠ The break fact is `break_started_at`, NOT `status`. F36 makes
    // `occupied` win the status while the timestamp stays on the wire, so
    // deriving it from `status` leaves a staffer who forgot to end a break and
    // then claimed a room unable to end it from this screen at all: the control
    // would read «להפסקה», the tap would be a 200 no-op keeping the first
    // timestamp, and it would stay that way until she released the room.
    const onBreak = card.break_started_at !== null;
    setBusyIds((current) => [...current, card.id]);
    setCardError(null);
    restoreFocusRef.current = card.id;
    const failure = await mutate(async () => {
      const patched = onBreak
        ? await api.endStaffBreak(card.id)
        : await api.startStaffBreak(card.id);
      // NOT optimistic. The card is patched from the SERVER's card, so the panel
      // cannot disagree with itself — and on a no-op 200 (another staffer got
      // there first) that is what renders the FIRST timestamp rather than this
      // request's intent.
      const next = (cardsRef.current ?? []).map((item) =>
        item.id === patched.id ? patched : item,
      );
      cardsRef.current = next;
      setCards(next);
      setUpdatedAt(new Date().toISOString());
      // F-ok and F-noop announce the SAME sentence, deliberately: the outcome
      // she wanted is the outcome that holds, and telling her she lost a race
      // would be telling her she was wrong when she was right.
      setCue({
        text: t(onBreak ? "floor.breakEndedCue" : "floor.breakStartedCue", {
          name: patched.display_name,
        }),
        name: patched.display_name,
      });
    });
    setBusyIds((current) => current.filter((id) => id !== card.id));
    if (failure !== null) {
      // A 404 is NOT terminal: a colleague vanishing is a fact about her, not
      // about the viewer's access.
      setCardError({
        id: card.id,
        text:
          failure instanceof ApiError && failure.status === 404
            ? t("floor.error.notFound")
            : t("staff.loadFailed"),
      });
    }
  };

  const heading = (
    <h2 ref={headingRef} tabIndex={-1} className="text-lg font-semibold text-ink">
      {t("floor.heading")}
    </h2>
  );

  if (terminal !== null) {
    // The panel is over. Cards are cleared: a dead session cannot vouch for
    // them, and on the 403 the staff list is precisely what she is no longer
    // permitted to see. For the three floor roles this is the whole product
    // going dark (design.md F-7).
    return (
      <section className="space-y-6">
        {heading}
        <p role="alert" className="text-sm text-ink">
          {t(terminal === "session" ? "floor.sessionEnded" : "floor.accessEnded")}
        </p>
        <div>
          <Button variant="secondary" size="md" onClick={() => window.location.reload()}>
            {t("floor.reload")}
          </Button>
        </div>
      </section>
    );
  }

  const stopped = mode !== "running";
  // The freshness row — and therefore the SC 2.2.2 mechanism — renders whenever
  // there is anything to be current about. NOT in F-load: nothing is
  // auto-updating yet, so there is no content for a repaint to move and a pause
  // control over a skeleton pauses a fetch the user has not seen produce
  // anything. It DOES render in F-fail, because the loop is alive and backing
  // off, so a viewer who wants it to stop must be able to stop it.
  const showFreshness = cards !== null || loadFailed;

  const freshnessText = () => {
    if (updatedAt === null) {
      return null;
    }
    const time = jerusalemTime(updatedAt);
    if (stopped) {
      return isolateLtr(t("floor.pausedAt", { time }), time);
    }
    if (stale) {
      return isolateLtr(t("floor.staleAt", { time }), time);
    }
    return isolateLtr(t("floor.updatedAt", { time }), time);
  };

  const bodyLine = () => {
    if (mode === "paused") {
      return t("floor.paused");
    }
    if (mode === "idle") {
      return t("floor.idleStopped", { minutes: IDLE_STOP_MINUTES });
    }
    if (stale) {
      return t("floor.staleBody");
    }
    return null;
  };

  const body = bodyLine();

  // F-load announces itself: the shipped console says nothing while loading, and
  // this panel closes that for itself by reusing the region it already needs.
  // DERIVED rather than stored, so it cannot outlive the first payload — a cue
  // still reading «טוען…» under a rendered list would be a lie in a live region.
  const cueText =
    cue.text !== "" ? cue.text : cards === null && !loadFailed ? t("floor.loading") : "";

  return (
    <section className="space-y-4">
      {heading}

      {/* The cue: role="status", user-initiated outcomes ONLY. The poll may
          never write here — a status update every five seconds would announce
          the whole staff list forever (spec D12). */}
      <p
        ref={cueRef}
        data-testid="floor-cue"
        role="status"
        tabIndex={-1}
        className="text-sm text-ink-muted"
      >
        {/* ⚠ THE <p> IS NEVER REMOUNTED — only the keyed span inside it is. That
            asymmetry is the whole trick: a live region ADDED to the document is
            not announced, but a childList mutation INSIDE a region that was
            already there is. The `key` is `cue.nonce`, so a cue whose text
            repeats verbatim still replaces this node. See the writer for why. */}
        <span key={cue.nonce}>
          {cue.name === null ? cueText : isolateBidi(cueText, cue.name)}
        </span>
      </p>

      {showFreshness && (
        <div className="space-y-1">
          <div className="flex flex-wrap items-center justify-end gap-3 text-sm text-ink-muted">
            {/* FIRST STOP INSIDE THE PANEL, before any card: a 2.2.2 mechanism
                placed after the content it governs is reachable only by walking
                the list that is repainting under the walk.

                ONE button whose accessible name changes — never aria-pressed,
                which would read as two contradictory facts (a name saying
                "resume" and a pressed state saying "on"). */}
            <Button
              variant="ghost"
              size="md"
              fullWidthMobile={false}
              aria-label={t(stopped ? "floor.resumeAria" : "floor.pauseAria")}
              onClick={stopped ? resume : pause}
            >
              {t(stopped ? "floor.resume" : "floor.pause")}
            </Button>
            <span
              className={
                stopped || stale ? "font-semibold text-warning-text" : "text-ink-muted"
              }
            >
              {freshnessText()}
            </span>
          </div>
          {body !== null && (
            <div className="flex flex-wrap items-center justify-end gap-3">
              <p className="text-sm text-ink-muted">{body}</p>
              {/* «רענון» in the STALE case only. The resume control is the
                  affordance when stopped, and «רענון» beside «חידוש» is two
                  Hebrew words a hurried reader will not tell apart. */}
              {stale && !stopped && (
                <Button
                  variant="secondary"
                  size="md"
                  fullWidthMobile={false}
                  onClick={() => poll.refresh()}
                >
                  {t("floor.refresh")}
                </Button>
              )}
            </div>
          )}
        </div>
      )}

      {cards === null && !loadFailed && (
        <Card>
          <Skeleton variant="text" lines={3} />
        </Card>
      )}

      {loadFailed && cards === null && (
        <div className="space-y-3">
          {/* The OUTAGE register, and a SHIPPED key reused rather than a new
              floor.outage: staff.loadFailed is one sentence about the staff
              list, which is exactly what failed to load (design.md F-10). */}
          <p role="alert" className="text-sm text-ink-muted">
            {t("staff.loadFailed")}
          </p>
          {/* NOT while stopped. copy.md §2 forbids this adjacency by name:
              «רענון» beside «חידוש» is two Hebrew words a hurried reader will
              not tell apart, and the resume control is the affordance there.
              The stale branch above is guarded the same way. This state is new
              in F57 — the board cannot reach it, because BoardSection renders
              its freshness row only when rows !== null, whereas F-fail here
              renders it so a backing-off loop can still be stopped. */}
          {!stopped && (
            <Button
              variant="secondary"
              size="md"
              fullWidthMobile={false}
              onClick={() => poll.refresh()}
            >
              {t("floor.refresh")}
            </Button>
          )}
        </div>
      )}

      {/* ABOVE the rooms (spec D16): an active emergency outranks a room list.
          A CHILD for three reasons — it needs the staff list the raise dialog's
          target Select reads, it needs `paused` so the pause control does not
          lie, and it uses this panel's ONE role="status" cue and ONE SC 2.2.2
          control, so the board gains no third pause button. Its alerts come from
          the app-level poll, which is the one place this feature deliberately
          reaches past this component. */}
      <SosCentre
        selfId={selfId}
        role={role}
        paused={stopped}
        onCue={setCue}
        onRaise={(trigger) => openRaise(trigger, null)}
      />

      {/* ABOVE the staff list (spec D15): a staffer opens this screen to find a
          free room, so the staff cards are the reference and the rooms are the
          act. A CHILD and not a sibling — it rides this poll, this pause control
          and this announced region, and adds no second one of any of them. */}
      <RoomsPanel
        rooms={rooms}
        staff={cards}
        serverNow={serverNow}
        fetchCount={fetchCount}
        selfId={selfId}
        role={role}
        paused={stopped}
        mutate={mutate}
        onRooms={applyRooms}
        onCue={setCue}
        onRaise={openRaise}
        waitlistCount={waitlist?.entries.length ?? 0}
        onDispatch={applyDispatch}
      />

      {/* BELOW the rooms and ABOVE the staff list (spec D15). The stated reason
          — «the rooms are what she acts on, the queue is what she acts from» —
          is true and is not the load-bearing one: TAKE-NEXT LIVES ON A ROOM
          TILE, so a queue of forty above the tiles puts this feature's headline
          control two screens below the fold at 375, on the phone the brief calls
          the console. The panel order and the control's placement are ONE
          decision taken twice.

          A CHILD and not a sibling, for the third time on this screen: no poll,
          no pause control, no announced region and no freshness stamp of its
          own. */}
      <WaitlistPanel
        waitlist={waitlist}
        rooms={rooms}
        serverNow={serverNow}
        fetchCount={fetchCount}
        role={role}
        paused={stopped}
        mutate={mutate}
        onWaitlist={applyWaitlist}
        onRooms={applyRooms}
        onCue={setCue}
      />

      {cards !== null && (
        <Card>
          {cards.length === 0 ? (
            <EmptyState title={t("floor.empty")} />
          ) : (
            /* NO live attributes on the list. role="log" is the tempting wrong
               answer — it is for append-only chat and this list mutates in
               place. */
            <ul className="divide-y divide-border">
              {cards.map((card) => {
                // ⚠ THE BREAK FACT, and it is NOT `card.status` — see `toggle`.
                // `status` is a display precedence that F36 makes `occupied`
                // win; `break_started_at` is what says a break is open, and
                // both the control and the since-line follow it.
                const onBreak = card.break_started_at !== null;
                const badge = STATUS_BADGE[card.status];
                const isSelf = card.id === selfId;
                // Which control EXISTS is the rendered form of D6's two axes.
                // A non-elevated staffer sees a name, a role and a status on a
                // colleague's card and nothing else — no disabled button, no
                // lock glyph, no «אין לך הרשאה» line, no tooltip. The absence is
                // cosmetics; the control is the server's check.
                const mayToggle = isSelf || ELEVATED.has(role);
                const busy = busyIds.includes(card.id);
                const labelKey = roleLabelKey(card.role);
                return (
                  <li
                    key={card.id}
                    data-staff-id={card.id}
                    className="flex flex-col gap-3 py-4 sm:flex-row sm:items-center"
                  >
                    <div className="min-w-0 grow space-y-1">
                      <div className="flex flex-wrap items-center gap-2">
                        {/* Bare <bdi>, never dir="ltr": forcing LTR on a Hebrew
                            name reverses its words. No truncation and no
                            ellipsis on a display name, ever — a panel that
                            abbreviates a colleague's name makes two colleagues
                            look like one. */}
                        <bdi className="font-semibold break-words text-ink">
                          {card.display_name}
                        </bdi>
                        {isSelf && (
                          <span className="text-xs text-ink-muted">{t("staff.selfMarker")}</span>
                        )}
                        {/* ONE Badge per card, and it is the STATUS. The role is
                            muted words, so the card's single pill means one
                            thing. The WORD carries the state; the colour never
                            does. */}
                        <Badge variant={badge.variant}>{t(badge.labelKey)}</Badge>
                      </div>
                      <p className="text-sm text-ink-muted">
                        <bdi>{labelKey === null ? card.role : t(labelKey)}</bdi>
                      </p>
                      {/* THREE FRAGMENTS, each its own element, separated by the
                          console's existing «·» — never one interpolated
                          sentence. «בחדר {{room}}» would render «בחדר חדר 2»
                          against the boutique's own labels, and the string would
                          need two bidi isolations plus a numeric one from
                          helpers that cannot be chained.

                          The client's name is LABELLED rather than left bare:
                          a name one line under another name, separated by a
                          character most screen readers do not voice, is not a
                          readable value. */}
                      {card.occupancy !== null && serverNow !== null && (
                        <p className="text-sm text-ink">
                          <bdi>{card.occupancy.room_label}</bdi>
                          {" · "}
                          {card.occupancy.client_label === null ? (
                            t("rooms.anonymous")
                          ) : (
                            <>
                              <span className="text-ink-muted">{t("rooms.clientLabel")}</span>{" "}
                              <bdi>{card.occupancy.client_label}</bdi>
                            </>
                          )}
                          {" · "}
                          {elapsedLine(t, serverNow, card.occupancy.assigned_at)}
                        </p>
                      )}
                      {/* The since-line renders ONLY on an open break, which
                          F36 makes reachable on an OCCUPIED card for the first
                          time — the only place a screen can tell a shift
                          manager that a break was never closed. It is what
                          makes a forgotten break legible rather than silent,
                          since nothing but a tap ever ends one (D7). */}
                      {onBreak && card.break_started_at !== null && (
                        <p className="text-sm text-ink">
                          {isolateLtr(
                            t("floor.breakSince", {
                              time: jerusalemTime(card.break_started_at),
                            }),
                            jerusalemTime(card.break_started_at),
                          )}
                        </p>
                      )}
                      {cardError?.id === card.id && (
                        <p
                          ref={cardAlertRef}
                          role="alert"
                          tabIndex={-1}
                          className="text-sm text-danger"
                        >
                          {cardError.text}
                        </p>
                      )}
                    </div>
                    {mayToggle && (
                      <Button
                        ref={(node) => {
                          controlRefs.current.set(card.id, node);
                        }}
                        variant={onBreak ? "ghost" : "secondary"}
                        size="md"
                        fullWidthMobile={false}
                        loading={busy}
                        // The accessible name carries the visible label PLUS the
                        // person: five buttons all named «להפסקה» is a screen
                        // reader dead end. No bidi treatment — an aria-label
                        // takes no markup, so there is nothing to reorder.
                        aria-label={t(onBreak ? "floor.breakEndAria" : "floor.breakStartAria", {
                          name: card.display_name,
                        })}
                        onClick={() => void toggle(card)}
                      >
                        {t(onBreak ? "floor.breakEnd" : "floor.breakStart")}
                      </Button>
                    )}
                  </li>
                );
              })}
            </ul>
          )}
        </Card>
      )}

      {/* Conditionally MOUNTED and not merely closed: `Modal` renders its
          <dialog> unconditionally, so an always-mounted one would add a third
          node to every `queryAllByRole("dialog")` on this screen — which is the
          shape RoomsPanel's own two dialogs already avoid. */}
      {raiseOpen && (
        <SosRaiseDialog
          open
          staff={cards ?? []}
          selfId={selfId}
          assignmentId={raiseAssignmentId}
          onCue={setCue}
          onClose={() => setRaiseOpen(false)}
        />
      )}
    </section>
  );
}
