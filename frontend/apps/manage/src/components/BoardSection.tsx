import { Fragment, useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { Badge, Button, Card, EmptyState, Skeleton } from "@boutique/ui";
import { api, ApiError } from "../api";
import type { OwnerBookingDetail, OwnerBookingRow } from "../api";
import { bookingErrorText, isolateLtr, statusBadge } from "../lib/booking";
import { jerusalemTime, plainDate, todayJerusalem } from "../lib/jerusalem";

// P-1 / spec Q-1. One client constant: if the pilot or F29 says five seconds is
// too expensive, halving the load is this line and the UI does not change.
const POLL_INTERVAL_MS = 5_000;
// D4(6)'s cap, doubling from the base. D3 declines a server-side read limiter
// on this router — there is no attacker, only a fleet of loyal boards pointed
// at a sick server — so the throttle has to be the client's or there is none.
const MAX_BACKOFF_MS = 60_000;
// P-8, resolved by the implementation plan (C3) rather than by the user, and
// carried in the run report as a one-line overturn. NOT the prototype's 45
// seconds: that window exists so the state is reachable in a review, and
// shipping it would read as a bug.
const IDLE_STOP_MS = 600_000;
const IDLE_STOP_MINUTES = IDLE_STOP_MS / 60_000;
// Mirrors BOOKING_LIST_DEFAULT_LIMIT and deliberately NOT the server's maximum:
// the router declares le=BOOKING_LIST_MAX_LIMIT, so a client pinned to today's
// ceiling would start 422-ing the day the ceiling drops. Ask for fifty, and say
// so when the day is bigger.
const PAGE_LIMIT = 50;

type Mode = "running" | "paused" | "idle";
type Terminal = "session" | "access";

// The terminal set is {401, 403}, not {401}. Deactivation ends in a 401
// (staff_users.by_id filters deleted_at, resolve_session returns None); a
// mid-shift DEMOTION ends in a 403 (the session resolves fine and RoleGate
// raises). A board that stopped only on the 401 would keep polling a revoked
// role forever while the demotion had no visible effect — silently defeating
// "a role change bites on the very next request" on the one screen in the
// product that keeps making requests after a revocation.
function terminalOf(error: unknown): Terminal | null {
  if (!(error instanceof ApiError)) {
    return null;
  }
  if (error.status === 401) {
    return "session";
  }
  return error.status === 403 ? "access" : null;
}

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
  const [terminal, setTerminal] = useState<Terminal | null>(null);
  const [mode, setMode] = useState<Mode>("running");
  const [cue, setCue] = useState("");
  const [busyIds, setBusyIds] = useState<readonly string[]>([]);
  const [stranded, setStranded] = useState<readonly string[]>([]);
  const [rowError, setRowError] = useState<{ id: string; text: string } | null>(null);

  const cueRef = useRef<HTMLParagraphElement>(null);
  const dividerRef = useRef<HTMLLIElement>(null);
  const scrolledRef = useRef(false);
  // The timer always calls the LATEST tick, so the loop reads current state
  // without a ref mirror of every field it needs.
  const tickRef = useRef<() => void>(() => {});
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const idleRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const backoffRef = useRef(POLL_INTERVAL_MS);
  // One monotonic generation. A poll applies its result only if the generation
  // it was issued under is unchanged; mutations, the date roll, the manual
  // retry and resume all bump it.
  const generationRef = useRef(0);
  const dayRef = useRef(day);
  const runningRef = useRef(true);
  const rowsRef = useRef<OwnerBookingRow[] | null>(null);
  const mutationsRef = useRef(0);
  const holdRef = useRef(false);

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
    // so an unpaused loop would silently become a slow one and the board would
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
      // Names the cause: the difference between "I paused this" and "this
      // paused itself" is the whole difference between a control and a bug.
      setCue(t("board.idleStopped", { minutes: IDLE_STOP_MINUTES }));
    }, IDLE_STOP_MS);
  };

  const stop = (next: Terminal) => {
    runningRef.current = false;
    clearTick();
    clearIdle();
    setTerminal(next);
  };

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
    setStranded(held.map((item) => item.id));
  };

  const load = async (targetDay: string) => {
    const generation = generationRef.current;
    try {
      const result = await api.listBookings({ date: targetDay, offset: 0, limit: PAGE_LIMIT });
      if (generation !== generationRef.current) {
        return;
      }
      applyRows(result.items);
      setTotal(result.total);
      // The freshness claim changes ONLY on a success, which is what makes it a
      // claim the board can keep.
      setUpdatedAt(new Date().toISOString());
      setStale(false);
      setLoadFailed(false);
      backoffRef.current = POLL_INTERVAL_MS;
    } catch (error) {
      if (generation !== generationRef.current) {
        return;
      }
      const end = terminalOf(error);
      if (end !== null) {
        stop(end);
        return;
      }
      // Stale-and-labelled beats empty: blanking to the outage message would
      // throw away correct data to report a network fault.
      if (rowsRef.current === null) {
        setLoadFailed(true);
      } else {
        setStale(true);
      }
      backoffRef.current = Math.min(backoffRef.current * 2, MAX_BACKOFF_MS);
    } finally {
      // schedule() no-ops once the loop is stopped, so a terminal, a pause and
      // an idle stop all fall out of the same guard.
      if (generation === generationRef.current && mutationsRef.current === 0) {
        schedule(backoffRef.current);
      }
    }
  };

  const tick = () => {
    if (!runningRef.current || document.hidden || mutationsRef.current > 0) {
      return;
    }
    // A pointerdown holds the NEXT repaint and is consumed by it: an arrival
    // line appearing on an earlier row grows it and slides every control below
    // it, so a finger already travelling toward row 9 can land on the row above
    // or on nothing. Consumed rather than latched, so a lost pointerup costs
    // one interval and can never stall the board.
    if (holdRef.current) {
      holdRef.current = false;
      schedule(backoffRef.current);
      return;
    }
    // Recomputed every tick, never captured at mount: a counter tablet crosses
    // midnight and would otherwise keep asking for yesterday.
    const today = todayJerusalem();
    if (today !== dayRef.current) {
      dayRef.current = today;
      generationRef.current += 1;
      setDay(today);
    }
    void load(dayRef.current);
  };

  useEffect(() => {
    tickRef.current = tick;
  });

  useEffect(() => {
    void load(dayRef.current);
    return () => {
      clearTick();
      clearIdle();
    };
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
      // Fetch at once rather than waiting out an interval: the board is stale
      // by however long it was hidden, and five more seconds of a wrong board
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
  }, []);

  useEffect(() => {
    // Into view on the FIRST load and never again: scrolling the page under a
    // user who is reading it is the cardinal sin of a self-updating screen, and
    // the divider moving down the list as the day passes is enough.
    if (scrolledRef.current || dividerRef.current === null) {
      return;
    }
    scrolledRef.current = true;
    dividerRef.current.scrollIntoView?.({ block: "center" });
  });

  const pause = () => {
    runningRef.current = false;
    clearTick();
    clearIdle();
    setMode("paused");
    setCue(t("board.paused"));
  };

  const resume = () => {
    runningRef.current = true;
    setMode("running");
    // A resume is a fresh user intent, not a continuation of a backed-off
    // retry: a control that inherited a sixty-second gap would look like a
    // control that did not work.
    backoffRef.current = POLL_INTERVAL_MS;
    generationRef.current += 1;
    setCue(t("board.resumed"));
    armIdle();
    clearTick();
    void load(dayRef.current);
  };

  const retry = () => {
    generationRef.current += 1;
    clearTick();
    void load(dayRef.current);
  };

  const mutate = async (booking: OwnerBookingRow, kind: "in" | "undo") => {
    setBusyIds((current) => [...current, booking.id]);
    setRowError(null);
    mutationsRef.current += 1;
    // The loop issues no tick while a mutation is in flight, so the row cannot
    // be repainted underneath the request; the bump discards the one poll that
    // could still be in the air.
    clearTick();
    generationRef.current += 1;
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
      const end = terminalOf(error);
      if (end !== null) {
        stop(end);
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
        schedule(backoffRef.current);
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
                  control = <span className="text-sm text-ink-muted">{t("board.movedAway")}</span>;
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
                            <p role="alert" tabIndex={-1} className="text-sm text-danger">
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
