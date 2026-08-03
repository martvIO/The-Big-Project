import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Badge, Button, Card, EmptyState, Select } from "@boutique/ui";
import { api, ApiError } from "../api";
import type { Room, Waitlist, WaitlistEntry } from "../api";
import { isolateBidi, isolateLtr } from "../lib/booking";
import { elapsedMinutes } from "../lib/elapsed";

// F58. One row per waiting walk-in, inside FloorPanel and UNDER ITS POLL.
//
// **A CHILD, not a sibling** (spec D15), and RoomsPanel's contract applied a
// second time — which is what makes the pattern reviewable rather than a
// one-off: no usePoll instance, no timer, no pause control and no announced
// region of its own. Three things fall out and each is an a11y win rather than
// an architectural convenience: ONE SC 2.2.2 mechanism now governing three
// repainting regions, ONE role="status" so a room cue and a dispatch cue cannot
// talk over each other, and ONE freshness claim that is true of the staff, the
// rooms and the queue simultaneously because they arrive in one response.
//
// ⚠ Which control EXISTS is the rendered form of the authorization axes. A 403
// is TERMINAL for the whole floor screen, and for the three floor roles that is
// the entire product going dark — so «דלגי» and «הסרה» are ABSENT for them, not
// disabled and not explained. The product cost is real and recorded rather than
// softened into a tooltip: a reception staffer cannot skip a no-show or remove a
// duplicate; she asks a shift manager (spec D11 — the role gate is all-five or
// exactly-two, and a three-role gate is structurally forbidden by
// test_staff_role_gating.py's intersection classifier).
//
// ⚠ THE ROW CARRIES F33'S CAPABILITY AND MUST NEVER RENDER IT AS A LINK.
// `entry.id` is the ticket id, which is what /q/{id} authenticates with. It is
// on this payload because every verb takes it as the target and there is no
// lesser id; it is never an href, a `to`, or anything a browser will follow
// (spec A29).

const ELEVATED = new Set(["owner", "shift_manager"]);

// The DB pins this exact set (F33's migration). The OMIT branch on an
// unrecognised value is deliberate and copies the tile's `roleLabelKey` rule: a
// raw slug beside a customer's name is noise, and a wrong label is worse than a
// missing one on the panel where a name decides who gets removed.
const VISIT_KEY: Record<string, string> = {
  bride: "waitlist.visitBride",
  evening: "waitlist.visitEvening",
};

type Verb = "call" | "assign" | "skip" | "remove";

// A refused verb, scoped to its row. `value` is the ONE interpolated run the
// sentence carries — a colleague's name or a room label — which has to render
// inside a bare <bdi> and cannot be found in a flat string after the fact.
// `outage` picks the register: a mapped code is a NOTICE
// (--color-warning-text), an unmapped one is an OUTAGE (--color-ink-muted).
// Never --color-danger: nothing that can go wrong on this surface is her fault,
// and the only danger in this feature is the remove confirm's own button.
interface RowError {
  id: string;
  text: string;
  value: string | null;
  outage: boolean;
}

// ONE reveal on the whole panel, exactly as RoomsPanel keeps ONE openDialog —
// not one boolean per row. With up to a hundred rows, per-row state is a hundred
// chances for two open confirms to be co-visible, and two questions on one
// screen is a screen that has asked the user which of two irreversible acts she
// meant.
interface Reveal {
  entryId: string;
  kind: "assign" | "skip" | "remove";
}

// MOVE 3, and it has TWO triggers rather than the departure RoomsPanel's tiles
// have.
//
// A row leaves the list on a removal, on a second skip, or on a POLL TICK —
// another manager dispatching her from her own device, with no action by this
// user at all. And a successful FIRST skip does not remove the row: it MOVES it
// to the end. Rows are keyed by `entry.id`, so the browser keeps focus on the
// same control — now at position 40, below the fold, where a focus ring is
// indistinguishable from lost focus for exactly the user who most needs it.
//
// ⚠ The travelled arm is gated on `actedOn`, the entry THIS user just skipped.
// Without that gate a colleague's remove renumbers every row below it and would
// yank focus to the heading with no action by her — and a row that appears,
// moves or vanishes because somebody else acted must repaint silently.
function focusRescueNeeded(
  previous: readonly WaitlistEntry[],
  incoming: readonly WaitlistEntry[],
  actedOn: string | null,
): boolean {
  const active = document.activeElement;
  if (!(active instanceof Element)) {
    return false;
  }
  const held = active.closest("[data-entry-id]")?.getAttribute("data-entry-id");
  if (held === undefined || held === null) {
    return false;
  }
  const after = incoming.find((entry) => entry.id === held);
  if (after === undefined) {
    return true;
  }
  if (held !== actedOn) {
    return false;
  }
  const before = previous.find((entry) => entry.id === held);
  return before !== undefined && before.position !== after.position;
}

interface WaitlistPanelProps {
  /** The waiting walk-ins in the server's own order, or null on the first tick. */
  waitlist: Waitlist | null;
  /**
   * The same payload's rooms. The assign reveal's options are built from THIS
   * and not from a second request — RoomsPanel makes the identical argument for
   * building its handover list from `staff`. No picker endpoint, and one less
   * thing that can be a tick out of date.
   */
  rooms: Room[] | null;
  /** The envelope's own instant — the wait-time anchor, never the device clock. */
  serverNow: string | null;
  /**
   * How many ticks have SUCCEEDED. A counter and not the payload, because the
   * row alert's promise («הרשימה תתוקן בעדכון הבא») is kept by the update
   * happening and not by the update differing.
   */
  fetchCount: number;
  role: string;
  /** `mode !== "running"`. A stopped panel has no next update to promise. */
  paused: boolean;
  /** FloorPanel's shared five-part dance. Null means done, anything else is the error. */
  mutate: (fn: () => Promise<void>) => Promise<unknown>;
  /**
   * An UPDATER and never a finished list, for `onRooms`'s reason — and note
   * what it does NOT buy here: every verb on this panel answers the WHOLE
   * `Waitlist`, because a skip REORDERS it and a remove SHORTENS it and a
   * per-entry patch can express neither (spec Decision 11). So each call site
   * below ignores `current` and installs the server's list wholesale. The
   * signature is the parent's, which also moves the freshness stamp.
   *
   * ponytail: last-response-wins across two rows in flight together; the ≤5s
   * tick is the repair. A merge would need to know which of two whole lists is
   * newer, which is not knowable client-side.
   */
  onWaitlist: (update: (current: Waitlist) => Waitlist) => void;
  /** The dispatch half of a push-assign: its response carries the tile too. */
  onRooms: (update: (current: Room[]) => Room[]) => void;
  onCue: (cue: { text: string; name: string | null }) => void;
}

export function WaitlistPanel({
  waitlist,
  rooms,
  serverNow,
  fetchCount,
  role,
  paused,
  mutate,
  onWaitlist,
  onRooms,
  onCue,
}: WaitlistPanelProps) {
  const { t } = useTranslation();

  // ⚠ KEYED BY ENTRY ID, never by index. Rows are keyed by entry.id too, so a
  // repaint mutates text nodes inside a stable element — and a tick that
  // reorders the queue under an open reveal leaves the selection alone. Keyed by
  // position, the same tick's reorder would bind the next dispatch to the wrong
  // woman with no error anywhere.
  const [busy, setBusy] = useState<Record<string, Verb>>({});
  const [roomPick, setRoomPick] = useState<Record<string, string>>({});
  const [rowError, setRowError] = useState<RowError | null>(null);
  const [openReveal, setOpenReveal] = useState<Reveal | null>(null);

  const headingRef = useRef<HTMLHeadingElement>(null);
  const rowAlertRef = useRef<HTMLParagraphElement>(null);
  // The row's CURRENT primary control, by entry id — «קראי», which every role
  // has and which survives every success that leaves the row in place. Keyed by
  // id and not held as one ref because a reveal opening and closing changes the
  // row's shape, so React may or may not reuse the DOM node.
  const controlRefs = useRef(new Map<string, HTMLButtonElement | null>());
  const revealTriggerRef = useRef<HTMLButtonElement | null>(null);
  const revealFocusRef = useRef<HTMLElement | null>(null);
  const restoreFocusRef = useRef<string | null>(null);
  const reclaimFocusRef = useRef<string | null>(null);
  const focusHeadingRef = useRef(false);
  const travelledRef = useRef<string | null>(null);
  const entriesRef = useRef<readonly WaitlistEntry[] | null>(null);
  const fetchRef = useRef(fetchCount);

  // ⚠ BOTH OF THESE RUN DURING RENDER, because this is the only moment the old
  // DOM and the new list exist together: by the time an effect runs the
  // departing row is already gone and the focused alert is already unmounted,
  // activeElement has dropped to <body>, and the question cannot be asked any
  // more. Copied from RoomsPanel, and the reason is not style.
  if (fetchRef.current !== fetchCount) {
    fetchRef.current = fetchCount;
    // MOVE 6: the alert this tick is about to clear may be HOLDING FOCUS. It
    // promises «הרשימה תתוקן בעדכון הבא» and this is the update that keeps it —
    // about five seconds after the refusal, with NO USER ACTION AT ALL.
    // Removing a focused node drops activeElement to <body>, so her next Tab
    // restarts at the skip link.
    if (rowAlertRef.current !== null && document.activeElement === rowAlertRef.current) {
      reclaimFocusRef.current = rowError?.id ?? null;
    }
  }
  const entries = waitlist?.entries ?? null;
  if (entriesRef.current !== entries) {
    const previous = entriesRef.current;
    entriesRef.current = entries;
    if (previous !== null && entries !== null) {
      focusHeadingRef.current = focusRescueNeeded(previous, entries, travelledRef.current);
      travelledRef.current = null;
    }
  }

  useEffect(() => {
    // The row alert's own promise, kept: every successful tick clears it. Keyed
    // on the COUNTER and not on the list, because a tick that answers an
    // unchanged queue still kept the promise — and a failed tick never gets
    // here, so a refused verb's sentence survives exactly as long as the panel
    // has nothing newer to say.
    setRowError(null);
  }, [fetchCount]);

  useEffect(() => {
    // MOVE 1 — after a REFUSED verb, focus moves into the row's alert. Keyed on
    // the error state rather than raised inside the handler, because the alert
    // node does not exist yet when setRowError runs. THE FAILURE PATH IS THE ONE
    // THAT GETS FORGOTTEN: this bug class has shipped four times in this repo
    // and axe walked past every one, because axe cannot see a focus move that
    // never happened.
    if (rowError !== null) {
      rowAlertRef.current?.focus();
      return;
    }
    // MOVE 6 — …and when a tick CLEARS it while it held focus, hand focus back
    // to that row's own control, where she was when she tapped.
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
  }, [rowError]);

  useEffect(() => {
    // MOVE 2 — after a verb that SUCCEEDS AND LEAVES THE ROW IN PLACE (a call,
    // and a re-call that writes nothing), focus returns to the row's primary
    // control. @boutique/ui's Button is disabled={disabled || loading}, so a
    // real browser blurred the tapped control the instant the request started;
    // the body guard is what stops this stealing focus from wherever she moved
    // it in the meantime.
    //
    // ⚠ jsdom does NOT blur a disabled element, which is how F57 shipped a
    // vacuous version of this exact test — activeElement never became <body>,
    // the guard never passed, and the whole effect could be deleted with the
    // suite green. The test for this move blurs the tapped control explicitly.
    const pending = restoreFocusRef.current;
    if (pending === null || busy[pending] !== undefined) {
      return;
    }
    restoreFocusRef.current = null;
    // A row that LEFT or TRAVELLED is MOVE 3's, and it is about to fire.
    if (focusHeadingRef.current || document.activeElement !== document.body) {
      return;
    }
    // ⚠ NO heading fallback here, unlike RoomsPanel's MOVE 2. A row whose
    // control has gone is a row that LEFT, which is MOVE 3's whole subject —
    // and a duplicate rescue on this path makes MOVE 3's departure arm
    // untestable: the mutation that deletes the departing-row check comes back
    // green because this line quietly delivers the same outcome. One mechanism
    // per outcome, so the mutation can bite.
    controlRefs.current.get(pending)?.focus();
  }, [busy]);

  useEffect(() => {
    // MOVE 3 — a row that LEFT the list, or left its PLACE, while holding focus
    // hands focus to the panel heading. The flag is set during render, above,
    // because that is the only moment both lists exist.
    //
    // ⚠ NO `activeElement === document.body` guard, and that is the divergence
    // from RoomsPanel's MOVE 3 rather than an omission: the travelled row is
    // STILL MOUNTED and still holds focus, so a body guard would stand down on
    // the half of this move F-8 exists for. `focusRescueNeeded` has already
    // established that focus is inside the row in question.
    if (!focusHeadingRef.current) {
      return;
    }
    focusHeadingRef.current = false;
    headingRef.current?.focus();
  }, [waitlist]);

  useEffect(() => {
    // A tick that removes what the OPEN reveal is FOR. Two triggers: the row
    // itself is gone (another manager took her by take-next from her own
    // device), or the last free room went while an assign reveal was open — an
    // option-less <select> is a dead control that looks live, and a disabled one
    // is banned outright. Closing here hands the next effect the job of putting
    // focus somewhere real, which is MOVE 4 reached by a tick instead of a tap.
    if (openReveal === null || entries === null) {
      return;
    }
    const stillListed = entries.some((entry) => entry.id === openReveal.entryId);
    const freeRoomCount = (rooms ?? []).filter(
      (room) => room.assignment === null && room.is_active,
    ).length;
    if (!stillListed || (openReveal.kind === "assign" && freeRoomCount === 0)) {
      setOpenReveal(null);
    }
  }, [waitlist, rooms, openReveal, entries]);

  useEffect(() => {
    // MOVE 5 — a reveal that OPENS puts focus on the QUESTION (the room Select
    // for an assign), so a screen reader hears what is being asked rather than
    // an anonymous container.
    if (openReveal !== null) {
      revealFocusRef.current?.focus();
      return;
    }
    // MOVE 4 — a reveal that CLOSES returns focus to its trigger, falling back
    // to the heading when that trigger has gone (F51's shipped isConnected
    // shape). Without the fallback, focus lands on a detached node and silently
    // does nothing — which is what a tick-driven close always produces.
    const trigger = revealTriggerRef.current;
    if (trigger === null) {
      return;
    }
    revealTriggerRef.current = null;
    if (document.activeElement !== document.body) {
      return;
    }
    if (trigger.isConnected) {
      trigger.focus();
      return;
    }
    headingRef.current?.focus();
  }, [openReveal]);

  // The code-to-sentence map. NONE of these is red: a 409 is two managers
  // reaching for one customer and a 404 is a screen one tick behind, so both are
  // the NOTICE register.
  //
  // Takes NO verb discriminator, unlike RoomsPanel's `describe(error, target)`:
  // there the wire's one NOT_FOUND envelope covers three different things and
  // only the caller knows which it sent, whereas every code here already names
  // its own subject.
  const describe = (error: unknown): Omit<RowError, "id"> => {
    if (error instanceof ApiError && error.status === 409) {
      if (error.code === "QUEUE_TICKET_NOT_WAITING") {
        // ONE code, THREE remedies, chosen on details.status: go and find her in
        // a fitting room / there is nothing to do and the tick drops the row /
        // this one admits it does not know. `details` is optional on the wire,
        // which is what makes the third a requirement rather than a nicety.
        const status = error.details?.status;
        if (status === "in_service") {
          return {
            text: t("waitlist.error.QUEUE_TICKET_NOT_WAITING"),
            value: null,
            outage: false,
          };
        }
        return {
          text: t(status === undefined ? "waitlist.error.ticketNotWaitingUnknown" : "waitlist.error.ticketClosed"),
          value: null,
          outage: false,
        };
      }
      if (error.code === "QUEUE_TICKET_CHANGED") {
        // She is NOT removed; the press is refused. And the same tick that
        // clears this alert raises the rendered skip_count to 1, so her next
        // press correctly opens the confirm.
        return {
          text: t(
            paused
              ? "waitlist.error.queueTicketChangedPaused"
              : "waitlist.error.QUEUE_TICKET_CHANGED",
          ),
          value: null,
          outage: false,
        };
      }
      if (error.code === "ROOM_OCCUPIED") {
        // F36's two SHIPPED sentences, reused and NOT re-keyed. Four duplicated
        // Hebrew values one panel apart on one screen, with two floors and two
        // `ar` guards, would drift the first time anyone edited one.
        const name = error.details?.staff_display_name;
        return name === undefined
          ? { text: t("rooms.error.roomOccupiedUnknown"), value: null, outage: false }
          : { text: t("rooms.error.ROOM_OCCUPIED", { name }), value: name, outage: false };
      }
      if (error.code === "STAFF_OCCUPIED") {
        // ⚠ The SELF form. A row's push-assign carries no target staffer, so the
        // refusal is about the caller herself and the shipped third-person «היא
        // כבר בחדר אחר» would name nobody on the screen. Two new keys rather
        // than an edit of the shipped pair, whose literal is asserted in three
        // shipped suites.
        const room = error.details?.room_label;
        return room === undefined
          ? { text: t("rooms.error.staffOccupiedSelfUnknown"), value: null, outage: false }
          : { text: t("rooms.error.staffOccupiedSelf", { room }), value: room, outage: false };
      }
    }
    if (error instanceof ApiError && error.status === 404) {
      // pause() stops the loop and NOTHING else — every verb here stays fully
      // available while paused — so «הרשימה תתוקן בעדכון הבא» is then a promise
      // the screen will not keep. The paused twin points at «חידוש», which is
      // the control that IS on screen.
      return {
        text: t(paused ? "waitlist.error.notFoundPaused" : "waitlist.error.notFound"),
        value: null,
        outage: false,
      };
    }
    // A 5xx or a dropped request: the OUTAGE register, and a SHIPPED key rather
    // than errorMessage(error) leaking the server's English onto a Hebrew-only
    // surface.
    return { text: t("staff.loadFailed"), value: null, outage: true };
  };

  const act = async (entryId: string, verb: Verb, fn: () => Promise<void>): Promise<unknown> => {
    setBusy((current) => ({ ...current, [entryId]: verb }));
    setRowError(null);
    restoreFocusRef.current = entryId;
    const failure = await mutate(fn);
    setBusy((current) => {
      const { [entryId]: _done, ...rest } = current;
      return rest;
    });
    if (failure !== null) {
      // MOVE 1 owns the failure path; clearing this stops MOVE 2 grabbing focus
      // for one commit on its way past.
      restoreFocusRef.current = null;
      travelledRef.current = null;
      setRowError({ id: entryId, ...describe(failure) });
      // ⚠ THE COLLISION, resolved explicitly: setRowError and setOpenReveal land
      // in one commit, and the [rowError] effect is declared BEFORE the
      // [openReveal] one — so MOVE 1 focuses the alert and MOVE 4 then finds
      // activeElement off <body> and stands down. RoomsPanel.dialogFailed's
      // shape, one level in.
      setOpenReveal(null);
    }
    return failure;
  };

  const call = (entry: WaitlistEntry) => {
    void act(entry.id, "call", async () => {
      const next = await api.callQueueTicket(entry.id);
      onWaitlist(() => next);
      // A second call is a 200 that writes nothing — `called_at IS NULL` keeps
      // the FIRST timestamp — and the screen is identical to the first success,
      // deliberately: telling her she lost a race would be telling her she was
      // wrong when she was right.
      onCue({ text: t("waitlist.calledCue"), name: null });
    });
  };

  const assign = (entry: WaitlistEntry, roomId: string) => {
    void act(entry.id, "assign", async () => {
      const result = await api.assignFromQueue(roomId, { queue_ticket_id: entry.id });
      // BOTH panels patch from the server's own rows in one paint. A client that
      // patched only the tile and waited up to five seconds for the row to leave
      // would render the same woman as in-service AND waiting.
      onRooms((current) =>
        current.map((room) => (room.id === result.room.id ? result.room : room)),
      );
      onWaitlist(() => result.waitlist);
      setOpenReveal(null);
      // Names the ROOM and never her. The region is PERSISTENT — nothing clears
      // it, not a timer, not a tick, not an unmount — so her name in it would
      // outlive her row, and after she leaves the shop it would be the only
      // place it survives.
      onCue({
        text: t("waitlist.dispatchedCue", { room: result.room.label }),
        name: result.room.label,
      });
    });
  };

  const skip = (entry: WaitlistEntry) => {
    // ⚠ The count the client RENDERED, sent verbatim. It is what stops two
    // managers each tapping «דלגי» ONCE on a woman at skip_count 0 from removing
    // her with the confirm never shown on either device — the server refuses on
    // a mismatch rather than escalating.
    const seen = entry.skip_count;
    const removing = seen >= 1;
    if (!removing) {
      // A successful FIRST skip travels to the end of the list. MOVE 3's
      // travelled arm reads this.
      travelledRef.current = entry.id;
    }
    void act(entry.id, "skip", async () => {
      const next = await api.skipQueueTicket(entry.id, { seen_skip_count: seen });
      onWaitlist(() => next);
      setOpenReveal(null);
      // TWO cues for one control, chosen on what the CLIENT SENT — so it needs
      // nothing from a response that no longer carries her. A row that vanished
      // under «הועברה לסוף התור» would be the screen reporting the opposite of
      // what it did.
      onCue({ text: t(removing ? "waitlist.removedCue" : "waitlist.skippedCue"), name: null });
    });
  };

  const remove = (entry: WaitlistEntry) => {
    void act(entry.id, "remove", async () => {
      const next = await api.removeQueueTicket(entry.id);
      onWaitlist(() => next);
      setOpenReveal(null);
      onCue({ text: t("waitlist.removedCue"), name: null });
    });
  };

  const openFrom = (
    event: { currentTarget: HTMLButtonElement },
    kind: Reveal["kind"],
    entryId: string,
  ) => {
    revealTriggerRef.current = event.currentTarget;
    revealFocusRef.current = null;
    setOpenReveal({ entryId, kind });
  };

  const elevated = ELEVATED.has(role);
  const freeRooms = (rooms ?? []).filter((room) => room.assignment === null && room.is_active);

  // The h3 renders in EVERY state including the empty one, because it is MOVES
  // 3, 4 and 6's focus-rescue target and the rescue has to survive the
  // transition into and out of the EmptyState. tabIndex={-1} adds no tab stop.
  const heading = (
    <h3 ref={headingRef} tabIndex={-1} className="text-base font-semibold text-ink">
      {t("waitlist.heading")}
    </h3>
  );

  // W-load is FloorPanel's Skeleton: nothing is auto-updating yet and there is
  // no queue to be current about. No second skeleton and no second pause control
  // over a fetch nothing has seen produce anything.
  if (waitlist === null || entries === null) {
    return null;
  }

  return (
    <div className="space-y-3">
      {heading}

      {/* ⚠ PANEL-LEVEL and rendered ONCE. Forty identical sentences is not a
          design, and the fact is about the rooms rather than about any entry. It
          is the only surface that explains why «שבצי לחדר» vanished from every
          row and «קחי את הבאה» from every tile at the same moment. */}
      {entries.length > 0 && freeRooms.length === 0 && (
        <p className="text-sm text-ink-muted">{t("waitlist.noFreeRoom")}</p>
      )}

      <Card>
        {entries.length === 0 ? (
          // ⚠ NO body and NO action, for any role — the opposite of rooms.empty,
          // where the CTA is the whole point. There is nothing to configure: the
          // queue fills when a woman scans the printed QR at the door. This is
          // the state the panel is in for most of a boutique's day and it must
          // read as QUIET, never as broken and never as unconfigured.
          <EmptyState title={t("waitlist.empty")} />
        ) : (
          <ul className="divide-y divide-border">
            {entries.map((entry) => {
              const verb = busy[entry.id];
              const reveal = openReveal?.entryId === entry.id ? openReveal : null;
              const visitKey = VISIT_KEY[entry.visit_type];
              const minutes = serverNow === null ? null : elapsedMinutes(serverNow, entry.arrived_at);
              const waitLine =
                minutes === null
                  ? null
                  : minutes < 1
                    ? t("waitlist.waitingJustNow")
                    : isolateLtr(t("waitlist.waiting", { minutes }), String(minutes));
              // ⚠ THE SENT VALUE FOLLOWS THE LIST, not the map. A pick can
              // outlive the room it names — one tick and a colleague's claim —
              // and an unconditional read would dispatch her into a room the
              // screen does not show as selected.
              const picked =
                freeRooms.find((room) => room.id === roomPick[entry.id])?.id ??
                freeRooms[0]?.id ??
                "";
              return (
                <li
                  key={entry.id}
                  data-entry-id={entry.id}
                  className="flex flex-col gap-3 py-4 sm:flex-row sm:items-start"
                >
                  <div className="min-w-0 grow space-y-1">
                    <div className="flex flex-wrap items-center gap-2">
                      {/* tabular-nums keeps the name column flush from row 9 to
                          row 10. The number carries no label and is not
                          aria-hidden: «מקומך בתור» beside forty numbers is
                          exactly the repetition every other rule here prevents,
                          and the position is real information. */}
                      <bdi dir="ltr" className="text-sm tabular-nums text-ink-muted">
                        {entry.position}
                      </bdi>
                      {/* Bare <bdi>, NEVER dir="ltr" — forcing LTR on «נועה בר»
                          reverses its words, and it is the bidi defect that
                          looks deliberate. No truncation and no ellipsis, ever:
                          this is the panel where two abbreviated «נועה»s decide
                          who gets removed. */}
                      <bdi className="font-semibold break-words text-ink">{entry.name}</bdi>
                      {/* The row's ONE Badge, and it is her queue state. A second
                          pill in 295px teaches the reader to scan colours
                          instead of words. */}
                      {entry.called && <Badge variant="warning">{t("waitlist.called")}</Badge>}
                    </div>

                    {/* ⚠ elapsedMinutes and NEVER elapsedLine, which hard-codes
                        rooms.elapsed* and would render the ROOM's «כבר 42 דק'»
                        about a woman who has not been in a room — leaving this
                        feature's two keys dead, green and unused, because
                        i18n.test.ts counts entries and never checks that a key
                        is reached. Two sibling fragments around a «·» rather
                        than one sentence: the bidi helpers isolate ONE value
                        each and cannot be chained. */}
                    <p className="text-sm text-ink-muted">
                      {visitKey !== undefined && t(visitKey)}
                      {visitKey !== undefined && waitLine !== null && " · "}
                      {waitLine}
                    </p>

                    {/* MUTED, like the skip line and for the same reason: on a
                        row, --color-warning-text means "this is the answer to
                        what you just pressed", and the alert below is the only
                        thing that carries it. A sentence rather than a chip,
                        because the manager's question is WHICH of these two Noas
                        do I remove — and only a sentence can say the twin may
                        already be in a room. */}
                    {entry.duplicate && (
                      <p className="text-sm text-ink-muted">{t("waitlist.duplicate")}</p>
                    )}

                    {/* Context for the confirm that is about to appear, not an
                        alarm — the confirm is the guard. */}
                    {entry.skip_count >= 1 && (
                      <p className="text-sm text-ink-muted">{t("waitlist.skippedOnce")}</p>
                    )}

                    {/* The reveal, INSIDE the row's own <li> and never a
                        <dialog>. A <dialog> needs three focus mechanisms
                        RoomsPanel has already had to ship, none of which axe can
                        see, and this one lives in a row a tick can unmount
                        underneath it — so it would reproduce F57's shipped MAJOR
                        one level deeper again. A11y coverage is a reason to pick
                        the simpler element, not only a cost of the harder one. */}
                    {reveal !== null && reveal.kind === "assign" && (
                      <div className="space-y-3 pt-2">
                        {/* The value goes LAST because Select's `label` prop is
                            typed `string`, so isolation is IMPOSSIBLE rather
                            than merely omitted. min-h-11 at the call site
                            because Select declares no min-h-* at all, so cn()'s
                            plain join has no fight to lose. NO placeholder
                            option: a room is required, so the first free room is
                            preselected and visible. */}
                        <Select
                          ref={(node) => {
                            revealFocusRef.current = node;
                          }}
                          label={t("waitlist.assignRoom", { name: entry.name })}
                          className="min-h-11"
                          value={picked}
                          onChange={(event) =>
                            setRoomPick((current) => ({
                              ...current,
                              [entry.id]: event.target.value,
                            }))
                          }
                        >
                          {freeRooms.map((room) => (
                            <option key={room.id} value={room.id}>
                              {room.label}
                            </option>
                          ))}
                        </Select>
                        <div className="flex flex-col gap-3 sm:flex-row">
                          <Button
                            variant="secondary"
                            size="md"
                            loading={verb === "assign"}
                            onClick={() => assign(entry, picked)}
                          >
                            {t("waitlist.assignConfirm")}
                          </Button>
                          {/* The SHIPPED «ביטול». Nothing is being cancelled
                              about a person here — the act is not destructive —
                              so the plain word is correct and a second
                              declaration would be a duplicate value. */}
                          <Button variant="ghost" size="md" onClick={() => setOpenReveal(null)}>
                            {t("rooms.cancel")}
                          </Button>
                        </div>
                      </div>
                    )}

                    {reveal !== null && reveal.kind !== "assign" && (
                      <div className="space-y-3 pt-2">
                        <p
                          ref={(node) => {
                            revealFocusRef.current = node;
                          }}
                          tabIndex={-1}
                          className="text-base text-ink"
                        >
                          {isolateBidi(
                            t(
                              reveal.kind === "skip"
                                ? "waitlist.confirmSkip"
                                : "waitlist.confirmRemove",
                              { name: entry.name },
                            ),
                            entry.name,
                          )}
                        </p>
                        {/* ⚠ Only when she is flagged duplicate, and it is the
                            only mitigation Risk 2 has that the manager can act
                            on: whichever of her two tickets is removed, if it is
                            the one her tab polls, her phone renders «הביקור הזה
                            הסתיים.» and stops the loop while she is still in the
                            queue on the other one. True in both duplicate cases
                            — the twin may be another waiting row OR an
                            in_service ticket that appears nowhere on this
                            panel. */}
                        {reveal.kind === "remove" && entry.duplicate && (
                          <p className="text-sm text-ink-muted">
                            {t("waitlist.confirmRemoveDuplicate")}
                          </p>
                        )}
                        <div className="flex flex-col gap-3 sm:flex-row">
                          <Button
                            variant="danger"
                            size="md"
                            loading={verb === "skip" || verb === "remove"}
                            onClick={() =>
                              reveal.kind === "skip" ? skip(entry) : remove(entry)
                            }
                          >
                            {t("waitlist.confirmRemoveYes")}
                          </Button>
                          <Button variant="ghost" size="md" onClick={() => setOpenReveal(null)}>
                            {t("waitlist.confirmKeep")}
                          </Button>
                        </div>
                      </div>
                    )}

                    {rowError?.id === entry.id && (
                      <p
                        ref={rowAlertRef}
                        role="alert"
                        tabIndex={-1}
                        className={
                          rowError.outage
                            ? "text-sm text-ink-muted"
                            : "text-sm font-semibold text-warning-text"
                        }
                      >
                        {rowError.value === null
                          ? rowError.text
                          : isolateBidi(rowError.text, rowError.value)}
                      </p>
                    )}
                  </div>

                  {/* Four controls in 295px measure ≈320px, so they WRAP to a
                      second line rather than shrinking — fullWidthMobile={false}
                      on every one, because four full-width buttons per row would
                      be a wall. size="md" without exception: sm is min-h-9 = 36px
                      and under the house 44 floor, and this is the row in the
                      codebase where the temptation to reach for it is highest. */}
                  <div className="flex flex-wrap justify-end gap-3">
                    <Button
                      ref={(node) => {
                        controlRefs.current.set(entry.id, node);
                      }}
                      variant="ghost"
                      size="md"
                      fullWidthMobile={false}
                      loading={verb === "call"}
                      aria-label={t("waitlist.callAria", { name: entry.name })}
                      onClick={() => call(entry)}
                    >
                      {t("waitlist.call")}
                    </Button>
                    {/* Rendered only when at least one room is free and active;
                        the panel-level line above covers the other case. NEVER a
                        disabled button — a control that refuses is a 403's
                        cousin on a screen where 403 is terminal. */}
                    {freeRooms.length > 0 && (
                      <Button
                        variant="secondary"
                        size="md"
                        fullWidthMobile={false}
                        aria-label={t("waitlist.assignAria", { name: entry.name })}
                        onClick={(event) => openFrom(event, "assign", entry.id)}
                      >
                        {t("waitlist.assign")}
                      </Button>
                    )}
                    {/* One tap while skip_count is 0; the confirm once it is >= 1,
                        because a control that silently changes meaning on its
                        second press is the shape skip_count is on the wire to
                        prevent. */}
                    {elevated && (
                      <Button
                        variant="ghost"
                        size="md"
                        fullWidthMobile={false}
                        loading={verb === "skip" && reveal === null}
                        aria-label={t("waitlist.skipAria", { name: entry.name })}
                        onClick={(event) => {
                          if (entry.skip_count >= 1) {
                            openFrom(event, "skip", entry.id);
                            return;
                          }
                          skip(entry);
                        }}
                      >
                        {t("waitlist.skip")}
                      </Button>
                    )}
                    {/* DC-9: `secondary`, taking the shipped storefront
                        precedent rather than going one step below it — at 375
                        the wrapped four-button row then distinguishes the one
                        irreversible control by WEIGHT rather than by reading
                        order. The trigger is not `danger` because the trigger
                        ASKS rather than removes, and a permanently red control
                        on every row of a list of waiting customers reads as a
                        threat on a screen a staffer opens fifty times a shift.
                        The confirm pair keeps the shipped danger/ghost
                        pairing. */}
                    {elevated && (
                      <Button
                        variant="secondary"
                        size="md"
                        fullWidthMobile={false}
                        aria-label={t("waitlist.removeAria", { name: entry.name })}
                        onClick={(event) => openFrom(event, "remove", entry.id)}
                      >
                        {t("waitlist.remove")}
                      </Button>
                    )}
                  </div>
                </li>
              );
            })}
          </ul>
        )}

        {/* Names NO count and NO limit — both are the server's to change without
            a copy edit — and names what falls off instead, which is a fact she
            can act on. */}
        {waitlist.truncated && entries.length > 0 && (
          <p className="pt-4 text-sm text-ink-muted">{t("waitlist.truncated")}</p>
        )}
      </Card>
    </div>
  );
}
