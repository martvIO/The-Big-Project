import { Fragment, useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { Badge, Button, Card, EmptyState, Skeleton } from "@boutique/ui";
import { api, ApiError } from "../api";
import type { OwnerBookingDetail, OwnerBookingRow, WalkInBookingRequest } from "../api";
import { bookingErrorText, isolateLtr, statusBadge } from "../lib/booking";
import { jerusalemTime, plainDate, todayJerusalem } from "../lib/jerusalem";
import { IDLE_STOP_MINUTES, usePoll } from "../lib/usePoll";
import type { TickOutcome } from "../lib/usePoll";
import { WalkInDialog } from "./WalkInDialog";

// The poll's six mechanisms, its three constants and the {401,403} terminal
// classifier moved to lib/usePoll.ts in F57 — the second caller, which is the
// reopening condition F34's D13 named. Nothing about this component's behaviour
// changed, and BoardSection.test.tsx passing with a ZERO-LINE DIFF is the gate
// that says so.
//
// Mirrors BOOKING_LIST_DEFAULT_LIMIT and deliberately NOT the server's maximum:
// the router declares le=BOOKING_LIST_MAX_LIMIT, so a client pinned to today's
// ceiling would start 422-ing the day the ceiling drops. Ask for fifty, and say
// so when the day is bigger.
const PAGE_LIMIT = 50;

function holdsFocus(bookingId: string): boolean {
  const active = document.activeElement;
  if (!(active instanceof Element)) {
    return false;
  }
  return active.closest("[data-booking-id]")?.getAttribute("data-booking-id") === bookingId;
}

export function BoardSection() {
  const { t } = useTranslation();

  const [day, setDay] = useState(todayJerusalem);
  const [rows, setRows] = useState<OwnerBookingRow[] | null>(null);
  const [total, setTotal] = useState(0);
  const [updatedAt, setUpdatedAt] = useState<string | null>(null);
  const [stale, setStale] = useState(false);
  const [loadFailed, setLoadFailed] = useState(false);
  const [cue, setCue] = useState("");
  const [busyIds, setBusyIds] = useState<readonly string[]>([]);
  const [stranded, setStranded] = useState<readonly string[]>([]);
  const [rowError, setRowError] = useState<{ id: string; text: string } | null>(null);
  const [walkInOpen, setWalkInOpen] = useState(false);

  const cueRef = useRef<HTMLParagraphElement>(null);
  const movedRef = useRef<HTMLSpanElement>(null);
  const rowAlertRef = useRef<HTMLParagraphElement>(null);
  const dividerRef = useRef<HTMLLIElement>(null);
  const scrolledRef = useRef(false);
  const dayRef = useRef(day);
  const rowsRef = useRef<OwnerBookingRow[] | null>(null);
  // Kept in the caller, deliberately (D10). A `runExclusive` wrapper was
  // declined: `run` returning "suppressed" is the same observable behaviour —
  // zero requests during a mutation and NO timer armed during one — with a union
  // member instead of a three-member wrapper API.
  const mutationsRef = useRef(0);
  // Also the caller's: the pointer-hold POLICY is board-shaped, and the hook
  // deliberately does not supply it. FloorPanel writes its own.
  const holdRef = useRef(false);
  // The hook's `run` always calls the LATEST tick, so the loop reads current
  // state without a ref mirror of every field it needs — and `tick` may close
  // over `poll`, which does not exist until the line below.
  const tickRef = useRef<() => TickOutcome>(() => {});

  const poll = usePoll({
    run: () => tickRef.current(),
    // Names the cause: the difference between "I paused this" and "this paused
    // itself" is the whole difference between a control and a bug.
    onIdleStop: () => setCue(t("board.idleStopped", { minutes: IDLE_STOP_MINUTES })),
  });
  const { mode, terminal } = poll;

  const applyRows = (items: OwnerBookingRow[]) => {
    const current = rowsRef.current;
    if (current === null) {
      rowsRef.current = items;
      setRows(items);
      return;
    }
    // The only way a row leaves the day is a reschedule to another date —
    // cancelled rows stay. If the departing row holds focus, keep it in place
    // and say why; otherwise the browser drops focus to <body> for something
    // the user did not do, which is the one case a stable key cannot cover.
    const incoming = new Set(items.map((item) => item.id));
    const held = current.filter((item) => !incoming.has(item.id) && holdsFocus(item.id));
    const next = [...items];
    for (const item of held) {
      next.splice(Math.min(current.indexOf(item), next.length), 0, item);
    }
    rowsRef.current = next;
    setRows(next);
    if (held.length > 0 || stranded.length > 0) {
      setStranded(held.map((item) => item.id));
    }
  };

  const load = async (targetDay: string) => {
    const generation = poll.generation();
    try {
      const result = await api.listBookings({ date: targetDay, offset: 0, limit: PAGE_LIMIT });
      if (!poll.isCurrent(generation)) {
        return;
      }
      applyRows(result.items);
      setTotal(result.total);
      // The freshness claim changes ONLY on a success, which is what makes it a
      // claim the board can keep.
      setUpdatedAt(new Date().toISOString());
      setStale(false);
      setLoadFailed(false);
      // The row alert promises «השורה תתוקן בעדכון הבא» and this is the update
      // that keeps it. Without this the 409 line outlives the repaint that
      // already corrected the row — and on a row that repainted to `cancelled`
      // the control matrix leaves no way to clear it from that row at all.
      setRowError(null);
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
      if (rowsRef.current === null) {
        setLoadFailed(true);
      } else {
        setStale(true);
      }
      poll.failed();
    } finally {
      // reschedule() no-ops once the loop is stopped, so a terminal, a pause and
      // an idle stop all fall out of the same guard.
      if (poll.isCurrent(generation) && mutationsRef.current === 0) {
        poll.reschedule();
      }
    }
  };

  // The hook has already checked that the loop is running and the tab is
  // visible; what is left is the two board-shaped early returns D10 keeps here.
  const tick = (): TickOutcome => {
    if (mutationsRef.current > 0) {
      // Arms NOTHING. The single re-arm is mutate()'s own .finally().
      return "suppressed";
    }
    // A pointerdown holds the NEXT repaint and is consumed by it: an arrival
    // line appearing on an earlier row grows it and slides every control below
    // it, so a finger already travelling toward row 9 can land on the row above
    // or on nothing. Consumed rather than latched, so a lost pointerup costs
    // one interval and can never stall the board.
    if (holdRef.current) {
      holdRef.current = false;
      // Re-armed by the hook at the CURRENT gap, backoff untouched — a clean
      // tick would reset it to base and a held tick during a backoff would
      // start fetching at 5s.
      return "held";
    }
    // Recomputed every tick, never captured at mount: a counter tablet crosses
    // midnight and would otherwise keep asking for yesterday.
    const today = todayJerusalem();
    if (today !== dayRef.current) {
      dayRef.current = today;
      poll.bump();
      setDay(today);
    }
    void load(dayRef.current);
  };

  // Assigned during render, NOT in an effect, and that ordering is load-bearing:
  // usePoll's mount effect is registered before any effect in this component, so
  // an effect-assigned tickRef would still hold its no-op placeholder when the
  // hook fires the FIRST load — the board would mount empty and only populate
  // five seconds later. Writing it here means it is current before any effect
  // runs. The ref is never read during render, so this stays pure enough.
  tickRef.current = tick;

  useEffect(() => {
    // Keeping the departing row is only half the repair: the control we just
    // replaced WAS the focused element, so without this focus lands on <body>
    // anyway. Moving it to the note is a move inside the row she was already
    // in, not a jump — and it is the sentence she needs to read.
    if (stranded.length > 0 && document.activeElement === document.body) {
      movedRef.current?.focus();
    }
  }, [stranded]);

  // The symmetric half of the rescue at the end of mutate(): both controls carry
  // loading={busy}, and Button is disabled={disabled || loading}, so the browser
  // blurs the tapped control the instant the request starts. The success path
  // moves focus to the cue; on failure focus sat on <body> and the alert she
  // needs to read was never where her focus was (WCAG 2.4.3). Keyed on rowError
  // rather than raised in the catch, because the alert node does not exist yet
  // when setRowError runs — same shape as BookingDetail.tsx.
  useEffect(() => {
    if (rowError !== null) {
      rowAlertRef.current?.focus();
    }
  }, [rowError]);

  useEffect(() => {
    // Into view on the FIRST load and never again: scrolling the page under a
    // user who is reading it is the cardinal sin of a self-updating screen, and
    // the divider moving down the list as the day passes is enough. Armed by the
    // first rows arriving, NOT by the divider mounting: a board opened before
    // the day's first appointment renders no divider, and gating on the node
    // left the one shot loaded for whenever the clock later crossed a row.
    if (scrolledRef.current || rows === null) {
      return;
    }
    scrolledRef.current = true;
    dividerRef.current?.scrollIntoView?.({ block: "center" });
  }, [rows]);

  const pause = () => {
    poll.pause();
    setCue(t("board.paused"));
  };

  const resume = () => {
    setCue(t("board.resumed"));
    poll.resume();
  };

  const retry = () => poll.refresh();

  const mutate = async (booking: OwnerBookingRow, kind: "in" | "undo") => {
    setBusyIds((current) => [...current, booking.id]);
    setRowError(null);
    mutationsRef.current += 1;
    // The loop issues no tick while a mutation is in flight, so the row cannot
    // be repainted underneath the request; the bump discards the one poll that
    // could still be in the air.
    poll.clearTick();
    poll.bump();
    try {
      const detail: OwnerBookingDetail =
        kind === "in"
          ? await api.checkInBooking(booking.id)
          : await api.undoBookingCheckIn(booking.id);
      // NOT optimistic. The row is patched from the SERVER's row — one
      // round-trip of perceived speed traded for a check-mark that can never
      // un-tick, on the one surface whose whole job is answering "is she here".
      const patched = (rowsRef.current ?? []).map((item) =>
        item.id === detail.id ? detail : item,
      );
      rowsRef.current = patched;
      setRows(patched);
      setCue(
        t(kind === "in" ? "board.checkedInCue" : "board.undoneCue", {
          name: detail.customer_name,
        }),
      );
      // The tapped control unmounts — it becomes an arrival line — so without
      // this focus drops to <body>. The undo follows the same rule so there is
      // one rule instead of two.
      cueRef.current?.focus();
    } catch (error) {
      if (poll.fail(error)) {
        return;
      }
      setRowError({
        id: booking.id,
        // F-2: F15's Hebrew for this code says «כדאי לחזור לרשימה» — advice for
        // a detail screen you can back out of. The board has no list to go back
        // to and repairs itself on the next tick, so it owns this one string
        // and delegates every other code to the shared helper unchanged.
        text:
          error instanceof ApiError && error.code === "BOOKING_TRANSITION_INVALID"
            ? t("board.error.transitionInvalid")
            : bookingErrorText(error, t),
      });
    } finally {
      mutationsRef.current -= 1;
      setBusyIds((current) => current.filter((id) => id !== booking.id));
      // THE RE-ARM, and it lives in the .finally() rather than in the success
      // path on purpose: a rejected check-in must not park the loop either, or
      // the board silently stops converging the first time anybody acts.
      if (mutationsRef.current === 0) {
        poll.reschedule();
      }
    }
  };

  // F50. `mutate`'s discipline verbatim, with ONE deliberate difference and one
  // guard that difference forces.
  //
  // The difference: the re-arm is `poll.refresh()` and not `poll.reschedule()`.
  // A new row belongs at (starts_at, seat_index) order rather than at the head,
  // so patching it in client-side would mean writing a second sorter for a list
  // the server already orders and the next tick re-sorts anyway. One extra
  // request per walk-in — call it one an hour — buys the server's own ordering
  // and no divergence.
  //
  // ⚠ The guard: `reschedule()` NO-OPS while the loop is stopped, which is what
  // let F34 put its re-arm in an unguarded .finally(). `refresh()` has no such
  // guard — it is three unconditional statements — so on the 401/403 arm, where
  // the board's terminal screen has already taken over, an unguarded .finally()
  // fires one more request against a session already known to be dead. One local
  // flag, and no second classifier: `poll.fail` is the hook's.
  const create = async (body: WalkInBookingRequest): Promise<string | null> => {
    mutationsRef.current += 1;
    poll.clearTick();
    poll.bump();
    let terminated = false;
    try {
      const created = await api.createWalkInBooking(body);
      setWalkInOpen(false);
      setCue(t("walkin.createdCue", { name: created.customer_name }));
      // NO focus move here, unlike mutate(): the «תור חדש» trigger does not
      // unmount, so the native <dialog> returns focus to it on close and
      // stealing that for the cue would be a jump she did not ask for.
      return null;
    } catch (error) {
      if (poll.fail(error)) {
        terminated = true;
        return null;
      }
      return bookingErrorText(error, t);
    } finally {
      mutationsRef.current -= 1;
      if (mutationsRef.current === 0 && !terminated) {
        poll.refresh();
      }
    }
  };

  const heading = <h2 className="text-lg font-semibold text-ink">{t("board.heading")}</h2>;

  if (terminal !== null) {
    // The board is over. Rows are cleared: a dead session cannot vouch for them,
    // and on the 403 the day's list is precisely what she is no longer permitted
    // to see. The reload is a real remedy on the 401 and, on the 403, the honest
    // behaviour of a demotion biting on the very next request — which is why the
    // copy points at a person rather than implying the button will help.
    return (
      <div className="space-y-6">
        {heading}
        <p role="alert" className="text-sm text-ink">
          {t(terminal === "session" ? "board.sessionEnded" : "board.accessEnded")}
        </p>
        <div>
          <Button variant="secondary" size="md" onClick={() => window.location.reload()}>
            {t("board.reload")}
          </Button>
        </div>
      </div>
    );
  }

  const loading = rows === null && !loadFailed;
  const stopped = mode !== "running";
  const arrived = rows?.filter((item) => item.checked_in_at !== null).length ?? 0;
  const ratio = `${arrived}/${rows?.length ?? 0}`;
  const dayLabel = plainDate(day);
  const freshTime = updatedAt === null ? "" : jerusalemTime(updatedAt);
  // Precedence in the one inline-end slot: paused/idle beats stale, because a
  // stopped loop cannot fail a tick — the stop is the cause in force and the
  // resume control is the remedy. It also keeps «רענון» and «חידוש» off one
  // line, which is a copy problem solved by a state rule.
  const freshKey = stopped ? "board.pausedAt" : stale ? "board.staleAt" : "board.updatedAt";
  const nowMs = Date.now();
  const nowLabel = jerusalemTime(new Date(nowMs).toISOString());
  const dividerAt =
    rows === null ? -1 : rows.findIndex((item) => Date.parse(item.starts_at) > nowMs);
  // Absent when it would sit at the end (nothing ahead) or at the top (nothing
  // behind): in both cases it would mark nothing.
  const showDivider = dividerAt > 0;

  const bodyLine = stopped
    ? mode === "idle"
      ? t("board.idleStopped", { minutes: IDLE_STOP_MINUTES })
      : t("board.paused")
    : stale
      ? t("board.staleBody")
      : null;

  return (
    <div
      className="space-y-6"
      onPointerDown={() => {
        holdRef.current = true;
      }}
      onPointerUp={() => {
        holdRef.current = false;
      }}
      onPointerCancel={() => {
        holdRef.current = false;
      }}
    >
      {heading}
      {/* A board with no date picker must still say which day it shows. The one
          moment it matters is the counter tablet at 00:01, where the date
          rolling under an unattended screen would otherwise be invisible. */}
      <p data-testid="board-day" className="text-sm text-ink-muted">
        {isolateLtr(t("board.dayLine", { date: dayLabel }), dayLabel)}
      </p>

      {rows !== null && (
        // The whole live-ness contract, and it is NEVER announced — but it is
        // also never aria-hidden: that would make the board's only honesty
        // signal sighted-only, so a screen-reader user could never learn the
        // board stopped updating twenty minutes ago.
        <div
          data-testid="board-freshness"
          className="flex flex-wrap items-center justify-between gap-3 text-sm text-ink-muted"
        >
          <span data-testid="board-summary">
            {isolateLtr(t("board.summary", { ratio }), ratio)}
          </span>
          <span className="flex flex-wrap items-center gap-3">
            <span
              data-testid="board-updated"
              // P-6: correct-looking rows beside a muted grey notice are what
              // gets scanned past, and a board SHE paused is easier to forget
              // than one that broke. Still not text-danger — nothing here is
              // her fault and nothing here is hers to fix.
              className={stopped || stale ? "font-semibold text-warning-text" : undefined}
            >
              {isolateLtr(t(freshKey, { time: freshTime }), freshTime)}
            </span>
            {/* WCAG 2.0 SC 2.2.2 (Level A), and axe has no rule for it. One
                button whose NAME changes — not two, and not aria-pressed: a
                toggle that changes both its name and its pressed state reads as
                two contradictory facts. It is the first control inside the
                board, because a mechanism placed after the content it governs
                is reachable only by walking the list repainting under the walk. */}
            <Button
              variant="ghost"
              size="md"
              aria-label={t(stopped ? "board.resumeAria" : "board.pauseAria")}
              onClick={stopped ? resume : pause}
            >
              {t(stopped ? "board.resume" : "board.pause")}
            </Button>
          </span>
        </div>
      )}

      {bodyLine !== null && (
        <div className="flex flex-wrap items-center gap-3">
          <p data-testid="board-body" className="text-sm text-ink-muted">
            {bodyLine}
          </p>
          {/* No retry in the paused and idle states: the resume control IS the
              affordance, and «רענון» beside «חידוש» is two Hebrew words a
              hurried reader will not tell apart. */}
          {stale && !stopped && (
            <Button variant="secondary" size="md" onClick={retry}>
              {t("board.refresh")}
            </Button>
          )}
        </div>
      )}

      {rows !== null && (
        // F50. OUTSIDE the Card and outside the freshness bar, and both are
        // decisions. Not `EmptyState`'s `action` slot — that slot exists and
        // would hold a Button, but it renders ONLY when the day is empty, and
        // the bride at the counter arrives on a full board at least as often;
        // one button in one place beats the same button declared twice. Not in
        // the freshness bar either: «השהיה» beside «תור חדש» is a pause control
        // touching a create control, and a hurried thumb should not have those
        // adjacent.
        //
        // `terminal` needs no clause — that screen returns above.
        <div>
          <Button variant="secondary" size="md" onClick={() => setWalkInOpen(true)}>
            {t("board.newWalkIn")}
          </Button>
        </div>
      )}

      <WalkInDialog open={walkInOpen} onClose={() => setWalkInOpen(false)} onConfirm={create} />

      {/* The ONE announced region, and the poll may never write into it: a
          role="status" update every five seconds passes every automated check
          and is unusable. Everything it carries is the consequence of a tap —
          including the idle stop, whose trigger is her own inactivity. */}
      <p
        role="status"
        tabIndex={-1}
        ref={cueRef}
        data-testid="board-cue"
        className="text-sm text-ink-muted"
      >
        {loading ? t("board.loading") : cue}
      </p>

      {loadFailed && (
        <div className="flex flex-wrap items-center gap-3">
          <p role="alert" className="text-sm text-ink-muted">
            {t("board.loadFailed")}
          </p>
          {/* Unlike F15's list this screen has no date control to re-poke, so
              the retry is a real affordance and not a second tab stop. */}
          <Button variant="secondary" size="md" onClick={retry}>
            {t("board.refresh")}
          </Button>
        </div>
      )}

      {loading && <Skeleton variant="text" lines={4} />}

      {rows !== null && (
        // The Card's own p-6 is NOT overridden: cn() is a plain join and a
        // consumer p-0 loses to the baked-in p-6 (F15 F-6).
        <Card>
          {rows.length === 0 ? (
            <EmptyState title={t("board.emptyTitle")} body={t("board.emptyBody")} />
          ) : (
            // No live attributes at all. role="log" is the tempting wrong
            // answer: it is for append-only chat, and this list mutates in
            // place and re-sorts on the server.
            <ul className="divide-y divide-border">
              {rows.map((booking, index) => {
                const badge = statusBadge(booking.status);
                const time = jerusalemTime(booking.starts_at);
                const busy = busyIds.includes(booking.id);
                const label = { name: booking.customer_name, time };
                const arrival = booking.checked_in_at;

                let control: ReactNode = null;
                if (stranded.includes(booking.id)) {
                  control = (
                    <span
                      ref={movedRef}
                      tabIndex={-1}
                      data-testid="board-moved"
                      className="text-sm text-ink-muted"
                    >
                      {t("board.movedAway")}
                    </span>
                  );
                } else if (arrival !== null) {
                  // Always visible, never time-boxed: the server takes no clock
                  // bound and no status guard on the undo, so a control that
                  // vanished after five minutes would be a lie the API
                  // contradicts — and the remedy for a mis-tap would be psql.
                  control = (
                    <Button
                      variant="ghost"
                      size="md"
                      loading={busy}
                      aria-label={t("board.undoAria", label)}
                      onClick={() => void mutate(booking, "undo")}
                    >
                      {t("board.undo")}
                    </Button>
                  );
                } else if (booking.status === "confirmed") {
                  // Only the operation the server will accept: rendering four
                  // buttons where three answer 409 is a trap, and a disabled one
                  // with no explanation is worse than an absent one.
                  control = (
                    <Button
                      variant="secondary"
                      size="md"
                      loading={busy}
                      aria-label={t("board.checkInAria", label)}
                      onClick={() => void mutate(booking, "in")}
                    >
                      {t("board.checkIn")}
                    </Button>
                  );
                }

                return (
                  <Fragment key={booking.id}>
                    {showDivider && index === dividerAt && (
                      // A clock-derived visual landmark, so aria-hidden: it
                      // carries nothing a screen-reader user cannot get from
                      // the times, and unhidden it would inject a changing
                      // string into the middle of the list on every tick —
                      // the D11 hazard through the back door.
                      <li
                        ref={dividerRef}
                        aria-hidden="true"
                        data-testid="board-now"
                        className="border-t border-gold-strong pt-4 text-xs text-ink-muted"
                      >
                        {isolateLtr(t("board.now", { time: nowLabel }), nowLabel)}
                      </li>
                    )}
                    {/* Keyed by booking.id, so a repaint mutates text nodes
                        inside a stable element and focus inside a row survives
                        every tick. The row is NOT a button: one action per row,
                        and a row that is itself a button cannot contain one. */}
                    <li
                      data-booking-id={booking.id}
                      className="flex flex-col gap-3 py-4 sm:flex-row sm:items-center"
                    >
                      <div className="flex min-w-0 grow items-start gap-3">
                        <span className="w-14 shrink-0 font-semibold text-ink">
                          <bdi dir="ltr">{time}</bdi>
                        </span>
                        <div className="min-w-0 grow space-y-1">
                          <div className="flex flex-wrap items-center gap-2">
                            {/* Bare bdi: dir="ltr" on a Hebrew name is itself a
                                bidi defect, and it looks deliberate. No
                                ellipsis ever — a board that abbreviates a
                                bride's name makes two brides look like one. */}
                            <bdi className="font-semibold break-words text-ink">
                              {booking.customer_name}
                            </bdi>
                            <Badge variant={badge.variant} data-testid="board-status">
                              {t(badge.labelKey)}
                            </Badge>
                          </div>
                          <p className="text-sm text-ink-muted">
                            <bdi>{booking.appointment_type_name}</bdi>
                            {booking.source === "walk_in" && (
                              // F50. One muted word, in the attendance
                              // treatment: muted words, never a second Badge and
                              // never a tint. A walk-in row is an ordinary
                              // booking and every floor verb works on it — this
                              // says where it came from, nothing more.
                              <> · {t("booking.sourceWalkIn")}</>
                            )}
                            {booking.attendance_confirmed_at !== null && (
                              // Muted words, never a second Badge.
                              <> · {t("booking.attendanceConfirmed")}</>
                            )}
                            {booking.dress_name !== null && (
                              <>
                                {" · "}
                                <bdi>{booking.dress_name}</bdi>
                              </>
                            )}
                          </p>
                          {arrival !== null && (
                            // The row's operative fact, so ink and not muted —
                            // and words plus a time, never a tint, a dot or a
                            // check glyph. Spelled apart from the button on
                            // purpose, so «לא הגיעה» beside «נרשמה הגעה» reads
                            // as two true facts rather than a contradiction.
                            <p data-testid="board-arrival" className="text-sm text-ink">
                              {isolateLtr(
                                t("board.checkedInAt", { time: jerusalemTime(arrival) }),
                                jerusalemTime(arrival),
                              )}
                            </p>
                          )}
                          {rowError !== null && rowError.id === booking.id && (
                            // In the row, because a page-level error on a
                            // forty-row board names no bride.
                            <p
                              role="alert"
                              tabIndex={-1}
                              ref={rowAlertRef}
                              className="text-sm text-danger"
                            >
                              {rowError.text}
                            </p>
                          )}
                        </div>
                      </div>
                      <div className="flex shrink-0 justify-end sm:ms-3">{control}</div>
                    </li>
                  </Fragment>
                );
              })}
            </ul>
          )}
        </Card>
      )}

      {rows !== null && total > rows.length && (
        // Stated, never absorbed — a hidden bride is the one failure a board
        // may not have.
        <p data-testid="board-truncated" className="text-sm text-ink-muted">
          {isolateLtr(t("board.truncated", { count: rows.length }), String(rows.length))}
        </p>
      )}
    </div>
  );
}
