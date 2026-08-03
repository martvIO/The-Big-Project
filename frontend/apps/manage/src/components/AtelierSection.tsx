import { useEffect, useRef, useState } from "react";
import { Badge, Button, Card, cn, EmptyState, focusRing, Skeleton } from "@boutique/ui";
import { useTranslation } from "react-i18next";
import { api } from "../api";
import type { AtelierBoardResponse, AtelierTicket, TicketStage } from "../api";
import { isolateBidi, isolateLtr } from "../lib/booking";
import { jerusalemTime, plainDate } from "../lib/jerusalem";
import { bandLabel, laterStages, STAGE_LABEL_KEY, STAGE_ORDER } from "../lib/stages";
import { IDLE_STOP_MINUTES, usePoll } from "../lib/usePoll";
import type { TickOutcome } from "../lib/usePoll";

// F41. The atelier board: five named regions of named lists, one card per
// alteration ticket, and every move made by an explicit control.
//
// ⚠ THERE IS NO DRAG AND DROP ANYWHERE IN THIS TREE, AND THE BUTTON PATH IS NOT
// A FALLBACK — IT IS THE INTERFACE. Every accessible drag-and-drop is a
// keyboard-and-screen-reader alternative bolted onto a pointer gesture, so the
// button path gets built either way, and WCAG 2.5.7 requires the single-pointer
// alternative regardless. IS 5568 / WCAG 2.0 AA is a legal requirement on these
// screens, not a preference.
//
// ⚠ THE FIVE NULLABLE TIMESTAMPS ARE THE STATE MACHINE AND THERE IS NO STATUS
// COLUMN. `ticket.stage` is DERIVED by the server as the rightmost stamped
// column, floored at `intake`; `lib/stages.ts` owns the client's copy of that
// order. A NULL earlier stamp means "never separately recorded", not
// "impossible" — a ticket at `ready` with `in_progress_at` and `qc_at` NULL
// renders in the `ready` column with no annotation, because the board is not the
// place to explain a skip. `audit_log` is.
//
// This is the FOURTH caller of `lib/usePoll.ts` and it re-derives nothing: the
// single arming site, the document.hidden gate, the 5s->60s backoff, the
// {401,403} terminal classification, the idle stop and the monotonic generation
// all come from the hook. Four things are the CALLER's and are written here —
// the pointer hold, the mutation suppression, the generation bump before every
// write, and poll.fail() in every write's catch.

const ELEVATED = new Set(["owner", "shift_manager"]);

interface AtelierSectionProps {
  /** The signed-in staffer's id — the claim/release axis reads it. */
  selfId: string;
  /** Her role. Cosmetics only: the control is the server's D3/D9/D10 checks. */
  role: string;
}

function headingId(stage: TicketStage): string {
  return `atelier-h-${stage}`;
}

export function AtelierSection({ selfId, role }: AtelierSectionProps) {
  const { t } = useTranslation();

  const [boardData, setBoardData] = useState<AtelierBoardResponse | null>(null);
  const [updatedAt, setUpdatedAt] = useState<string | null>(null);
  const [stale, setStale] = useState(false);
  const [loadFailed, setLoadFailed] = useState(false);
  // The cue carries its interpolated NAME alongside its text, because the name
  // has to render inside a bare <bdi> and a flat string cannot say where it
  // starts. `name: null` is every cue that interpolates no person.
  const [cue, setCue] = useState<{ text: string; name: string | null }>({
    text: "",
    name: null,
  });
  const [busyIds, setBusyIds] = useState<readonly string[]>([]);

  const headingRef = useRef<HTMLHeadingElement>(null);
  // `load` runs outside render and would otherwise close over a stale payload.
  const boardRef = useRef<AtelierBoardResponse | null>(null);
  const mutationsRef = useRef(0);
  // The pointer hold is the CALLER's — usePoll deliberately does not supply it.
  // It matters more here than on the floor panel: a card changing column is a
  // LAYOUT change under a travelling finger, not a text swap, and it moves every
  // card below it in two columns at once.
  const holdRef = useRef(false);
  const tickRef = useRef<() => TickOutcome>(() => {});

  const poll = usePoll({
    run: () => tickRef.current(),
    onIdleStop: () =>
      setCue({ text: t("atelier.idleStopped", { minutes: IDLE_STOP_MINUTES }), name: null }),
  });
  const { mode, terminal } = poll;

  const applyBoard = (next: AtelierBoardResponse) => {
    boardRef.current = next;
    setBoardData(next);
  };

  const load = async () => {
    const generation = poll.generation();
    try {
      const result = await api.getAtelierBoard();
      if (!poll.isCurrent(generation)) {
        return;
      }
      applyBoard(result);
      // The freshness claim changes ONLY on a success, which is what makes it a
      // claim the board can keep.
      setUpdatedAt(new Date().toISOString());
      setStale(false);
      setLoadFailed(false);
      poll.succeeded();
    } catch (error) {
      if (!poll.isCurrent(generation)) {
        return;
      }
      if (poll.fail(error)) {
        return;
      }
      // Stale-and-labelled beats empty: blanking correct cards to report a
      // network fault throws away the boutique's whole work queue.
      if (boardRef.current === null) {
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

  useEffect(() => {
    // A pointerdown holds the NEXT repaint and is consumed by it. Consumed
    // rather than latched, so a lost pointerup costs at most one interval and
    // can never stall the board.
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

  // ⚠ THE CUE IS WRITTEN ONLY WHEN ITS VALUE ACTUALLY CHANGES. Assigning a
  // non-empty string to a text node runs the DOM's string-replace-all and
  // produces a real childList mutation inside role="status" EVEN WHEN THE TWO
  // STRINGS ARE BYTE-IDENTICAL. setCue with an equal value is a React no-op, so
  // the guard is the setState itself — and the poll never calls it at all.

  const pause = () => {
    poll.pause();
    setCue({ text: t("atelier.paused"), name: null });
  };

  const resume = () => {
    setCue({ text: t("atelier.resumed"), name: null });
    poll.resume();
  };

  /**
   * One card-level write. `send` answers the FULL ticket (or `null` for a
   * delete, whose card leaves), so the card is patched from the SERVER's own row
   * and the console cannot disagree with itself — and on a 200 no-op that
   * renders the FIRST actor's timestamp rather than this request's intent.
   *
   * NEVER OPTIMISTIC, for that reason.
   */
  const runWrite = async (
    ticket: AtelierTicket,
    send: () => Promise<AtelierTicket | null>,
    cueOf: (patched: AtelierTicket | null) => { text: string; name: string | null },
  ): Promise<boolean> => {
    setBusyIds((current) => [...current, ticket.id]);
    mutationsRef.current += 1;
    // The loop issues no tick while a write is in flight, so the card cannot be
    // repainted underneath the request; the bump discards the one poll that
    // could still be in the air.
    poll.clearTick();
    poll.bump();
    try {
      const patched = await send();
      const current = boardRef.current;
      if (current !== null) {
        applyBoard({
          ...current,
          tickets:
            patched === null
              ? current.tickets.filter((row) => row.id !== ticket.id)
              : current.tickets.map((row) => (row.id === patched.id ? patched : row)),
        });
      }
      setUpdatedAt(new Date().toISOString());
      setCue(cueOf(patched));
      return true;
    } catch (error) {
      // A write answering 403 is TERMINAL, on the same {401,403} rule the ticks
      // use. The alternative is an in-card alert plus a loop that keeps polling
      // with a role the server just refused. A 404 is NOT terminal — a ticket
      // vanishing is a fact about the ticket, not about her access.
      poll.fail(error);
      return false;
    } finally {
      mutationsRef.current -= 1;
      setBusyIds((current) => current.filter((id) => id !== ticket.id));
      // THE RE-ARM, in the .finally() rather than the success path: a refused
      // write must not park the loop either, or the board silently stops
      // converging the first time anybody acts.
      if (mutationsRef.current === 0) {
        poll.reschedule();
      }
    }
  };

  const advance = (ticket: AtelierTicket, stage: TicketStage) =>
    runWrite(
      ticket,
      () => api.advanceStage(ticket.id, stage),
      (patched) => ({
        text: t("atelier.cue.advanced", {
          name: patched?.customer_name ?? "",
          stage: t(STAGE_LABEL_KEY[patched?.stage ?? stage]),
        }),
        name: patched?.customer_name ?? null,
      }),
    );

  const heading = (
    <h2 ref={headingRef} tabIndex={-1} className="text-lg font-semibold text-ink">
      {t("atelier.heading")}
    </h2>
  );

  if (terminal !== null) {
    // The board is over. Cards are cleared: a dead session cannot vouch for
    // them, and on the 403 the board is exactly what she may no longer see.
    return (
      <section className="space-y-6">
        {heading}
        <p role="alert" className="text-sm text-ink">
          {t(terminal === "session" ? "atelier.sessionEnded" : "atelier.accessEnded")}
        </p>
        <div>
          <Button
            variant="secondary"
            size="md"
            fullWidthMobile={false}
            onClick={() => window.location.reload()}
          >
            {t("atelier.reload")}
          </Button>
        </div>
      </section>
    );
  }

  const stopped = mode !== "running";
  // The freshness row — and therefore the SC 2.2.2 mechanism — renders whenever
  // there is anything to be current about. NOT in A-load: nothing is
  // auto-updating yet, so a pause control there pauses a fetch the user has not
  // seen produce anything. It DOES render in A-fail, because the loop is alive
  // and backing off, so a viewer who wants it stopped must be able to stop it.
  const showFreshness = boardData !== null || loadFailed;

  const freshnessText = () => {
    if (updatedAt === null) {
      return null;
    }
    const time = jerusalemTime(updatedAt);
    if (stopped) {
      return isolateLtr(t("atelier.pausedAt", { time }), time);
    }
    if (stale) {
      return isolateLtr(t("atelier.staleAt", { time }), time);
    }
    return isolateLtr(t("atelier.updatedAt", { time }), time);
  };

  const bodyLine = () => {
    if (mode === "paused") {
      return t("atelier.paused");
    }
    if (mode === "idle") {
      return t("atelier.idleStopped", { minutes: IDLE_STOP_MINUTES });
    }
    if (stale) {
      return t("atelier.staleBody");
    }
    return null;
  };

  const body = bodyLine();

  // A-load announces itself: the shipped console says nothing while loading, and
  // this section closes that for itself by reusing the region it already needs.
  // DERIVED rather than stored, so it cannot outlive the first payload.
  const cueText =
    cue.text !== "" ? cue.text : boardData === null && !loadFailed ? t("atelier.loading") : "";

  const tickets = boardData?.tickets ?? [];
  // ONE grouped array, passed to the rail and to the columns. The counts are two
  // renderings of one source, never computed twice.
  const columns = STAGE_ORDER.map((stage) => ({
    stage,
    rows: tickets.filter((row) => row.stage === stage),
  }));

  const stageCount = (stage: TicketStage, total: number) => {
    // ⚠ `{{total}}`, NEVER `{{count}}`: `count` is i18next's plural-resolution
    // trigger, so passing it resolves `key_one`/`key_two`/`key_many` before the
    // base key. It renders correctly today and is one library upgrade away from
    // not — on a string that appears ten times per paint.
    const text = t("atelier.stageCount", { stage: t(STAGE_LABEL_KEY[stage]), total });
    return isolateLtr(text, String(total));
  };

  const seamstressOf = (id: string | null) =>
    id === null ? undefined : boardData?.seamstresses.find((row) => row.id === id);

  return (
    <section className="space-y-4">
      {heading}

      {showFreshness && (
        <div className="space-y-1">
          {/* FIRST STOP INSIDE THE SECTION, before any card: a 2.2.2 mechanism
              placed after the content it governs is reachable only by walking
              the list that is repainting under the walk.

              ONE button whose accessible name changes — never aria-pressed,
              which would read as two contradictory facts. */}
          <div className="flex flex-wrap items-center justify-end gap-3 text-sm text-ink-muted">
            <Button
              variant="ghost"
              size="md"
              fullWidthMobile={false}
              aria-label={t(stopped ? "atelier.resumeAria" : "atelier.pauseAria")}
              onClick={stopped ? resume : pause}
            >
              {t(stopped ? "atelier.resume" : "atelier.pause")}
            </Button>
            <span
              className={stopped || stale ? "font-semibold text-warning-text" : "text-ink-muted"}
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
                  {t("atelier.refresh")}
                </Button>
              )}
            </div>
          )}
        </div>
      )}

      {/* The cue: role="status", user-initiated outcomes ONLY. The poll may
          never write here — a status update every five seconds on a shared board
          would talk continuously for a whole shift. */}
      <p
        data-testid="atelier-cue"
        role="status"
        tabIndex={-1}
        className="text-sm text-ink-muted"
      >
        {cue.name === null ? cueText : isolateBidi(cueText, cue.name)}
      </p>

      {boardData === null && !loadFailed && (
        <Card>
          <Skeleton variant="text" lines={3} />
        </Card>
      )}

      {loadFailed && boardData === null && (
        <div className="space-y-3">
          {/* The OUTAGE register, and `atelier.loadFailed` is DECLARED rather
              than reused: the rule is «reuse a key whose NAMESPACE names its
              SUBJECT», and no shipped key names this one. */}
          <p role="alert" className="text-sm text-ink-muted">
            {t("atelier.loadFailed")}
          </p>
          {!stopped && (
            <Button
              variant="secondary"
              size="md"
              fullWidthMobile={false}
              onClick={() => poll.refresh()}
            >
              {t("atelier.refresh")}
            </Button>
          )}
        </div>
      )}

      {boardData !== null && boardData.tickets.length === 0 && (
        /* ⚠ THE FIRST THING EVERY NEW BOUTIQUE SEES. Five columns each reading
           «אין כרטיסים בשלב זה» is a wall of nothing that looks broken, so the
           columns AND the rail are replaced and the body teaches the five stage
           words in one sentence instead. The freshness row above still renders:
           a surface that has stopped updating must still be able to say so. */
        <EmptyState
          title={t("atelier.empty")}
          body={t("atelier.emptyBody")}
          action={
            <Button variant="primary" size="md" fullWidthMobile={false}>
              {t("atelier.newTicket")}
            </Button>
          }
        />
      )}

      {boardData !== null && boardData.tickets.length > 0 && (
        <>
          {boardData.truncated && (
            /* ⚠ THE CONSOLE NEVER STATES THE NUMBER. BOARD_TICKET_LIMIT is
               server-only and `truncated` is a FLAG precisely so it stays that
               way — a client that quoted 500 would be one constant away from
               lying. Ordering is due_date ascending, so what is missing is the
               LEAST urgent and the copy says so. */
            <p className="text-sm text-warning-text">{t("atelier.truncated")}</p>
          )}

          <div>
            <Button variant="primary" size="md" fullWidthMobile={false}>
              {t("atelier.newTicket")}
            </Button>
          </div>

          {/* THE STAGE RAIL — the pipeline at a glance AND the only way past a
              long column at 375. Plain <a href="#id"> anchors: fragment
              navigation to a tabindex="-1" target focuses it, which is exactly
              how ConsoleShell's shipped SkipLink reaches #console-main. So the
              rail moves focus AND scroll with no JavaScript, no scrollIntoView
              and no focus code.

              A NAMED landmark: a second navigation beside the shell's must be
              named or a screen-reader user cycling landmarks lands on two things
              both called "navigation". */}
          <nav aria-label={t("atelier.railAria")}>
            <ul className="flex flex-wrap gap-2">
              {columns.map(({ stage, rows }) => (
                <li key={stage}>
                  {/* A chip for an EMPTY column still renders «· 0» and still
                      links: a chip that vanishes is a control that moves under a
                      finger. `py-2 text-sm` lands near 40px, so min-h-11 is not
                      optional. */}
                  <a
                    href={`#${headingId(stage)}`}
                    className={cn(
                      "inline-flex min-h-11 items-center rounded-full border border-border px-3 py-2 text-sm text-ink",
                      focusRing,
                    )}
                  >
                    {stageCount(stage, rows.length)}
                  </a>
                </li>
              ))}
            </ul>
          </nav>

          {/* Two-up at >=768 and at 1440, one column at 375. There is no
              five-across view at ANY width and that is arithmetic, not taste:
              ConsoleShell caps content at 720px in three places, which leaves
              128px per column and 80px of card content — narrower than a
              Button reading «לשלב הבא». Lifting the cap is a console relayout
              owned by F42. */}
          <div className="grid gap-4 md:grid-cols-2 md:items-start">
            {columns.map(({ stage, rows }) => (
              <section
                key={stage}
                aria-labelledby={headingId(stage)}
                className="space-y-2"
              >
                <h3
                  id={headingId(stage)}
                  tabIndex={-1}
                  className="text-base font-semibold text-ink"
                >
                  {stageCount(stage, rows.length)}
                </h3>
                {/* NO live attributes on the lists. role="log" is the tempting
                    wrong answer — it is for append-only chat, and these lists
                    mutate in place and hand items to each other.

                    tabIndex={0} UNCONDITIONALLY at every width: the bounded
                    >=768 body is an overflow container and axe's
                    scrollable-region-focusable fires on exactly that. A resize
                    observer deciding an ARIA-relevant attribute is a mechanism
                    to keep true for a tab stop that costs nothing.

                    ⚠ RENDERED EVEN WHEN EMPTY, for the rail chip's reason: a
                    list — and its tab stop — that vanishes when a colleague
                    empties the column is a control that moves under a finger,
                    and an empty named list still announces «בקרה, רשימה, 0
                    פריטים» rather than leaving the column unnavigable. */}
                <ul
                  tabIndex={0}
                  aria-label={t(STAGE_LABEL_KEY[stage])}
                  className="space-y-3 md:max-h-[32rem] md:overflow-y-auto"
                >
                  {rows.map((ticket) => (
                    <TicketCard
                      key={ticket.id}
                      ticket={ticket}
                      bands={boardData.effort_bands}
                      seamstress={seamstressOf(ticket.assigned_staff_user_id)}
                      busy={busyIds.includes(ticket.id)}
                      role={role}
                      selfId={selfId}
                      onAdvance={advance}
                      t={t}
                    />
                  ))}
                </ul>
                {rows.length === 0 && (
                  /* The four other columns are the context that makes an empty
                     one legible rather than broken. */
                  <p className="text-sm text-ink-muted">{t("atelier.emptyColumn")}</p>
                )}
              </section>
            ))}
          </div>
        </>
      )}
    </section>
  );
}

type Translate = (key: string, options?: Record<string, unknown>) => string;

interface TicketCardProps {
  ticket: AtelierTicket;
  bands: AtelierBoardResponse["effort_bands"];
  seamstress: AtelierBoardResponse["seamstresses"][number] | undefined;
  busy: boolean;
  role: string;
  selfId: string;
  onAdvance: (ticket: AtelierTicket, stage: TicketStage) => void;
  t: Translate;
}

function TicketCard({
  ticket,
  bands,
  seamstress,
  busy,
  role,
  selfId,
  onAdvance,
  t,
}: TicketCardProps) {
  const later = laterStages(ticket.stage);
  // Which control EXISTS is COSMETICS and is asserted as cosmetics — the
  // server's D3/D9/D10 checks are the control. A seamstress may work her own
  // ticket or an unassigned one; on a colleague's she sees the facts and NO
  // CONTROLS AT ALL. Not a disabled button, not a lock glyph, not an «אין לך
  // הרשאה» line: a disabled control with no explanation is worse than an absent
  // one, an explanation would teach the permission model on a screen she opens
  // fifty times a shift, and either would be the client asserting a rule the
  // server owns.
  const mayWork =
    ELEVATED.has(role) ||
    (role === "seamstress" &&
      (ticket.assigned_staff_user_id === selfId || ticket.assigned_staff_user_id === null));

  const dressSize = ticket.dress_size;
  const date = plainDate(ticket.due_date);

  return (
    <li data-ticket-id={ticket.id}>
      <Card className="space-y-1">
        <div className="flex flex-wrap items-center gap-2">
          {/* Bare <bdi>, never dir="ltr": forcing LTR on «מיכל לוי» reverses its
              words. NO truncation, clipping, ellipsis or line-clamp anywhere on
              this card — a board that abbreviates two garments into the same
              string is worse than a tall card, and the same argument holds for a
              person. */}
          <bdi className="font-semibold break-words text-ink">{ticket.customer_name}</bdi>
          {/* EXACTLY ONE Badge per card and overdue owns it. The WORD is the
              signal and the border is reinforcement; the card itself gets
              nothing — no red border, no tint, no left rule, no icon, because on
              a 60-card column a wall of red stops meaning anything. A DELIVERED
              ticket is never overdue: the server cancels it, since a garment
              delivered late is history rather than a thing to chase. */}
          {ticket.overdue && <Badge variant="danger">{t("atelier.overdue")}</Badge>}
        </div>

        {/* Omitted entirely when both are null: an alteration on the bride's own
            gown has no catalog row, so absence is normal and is not an empty
            slot. */}
        {(ticket.dress_name !== null || dressSize !== null) && (
          <p className="text-sm break-words text-ink-muted">
            {ticket.dress_name !== null && <bdi>{ticket.dress_name}</bdi>}
            {ticket.dress_name !== null && dressSize !== null && " · "}
            {dressSize !== null &&
              (/^\d+$/.test(dressSize) ? <bdi dir="ltr">{dressSize}</bdi> : <bdi>{dressSize}</bdi>)}
          </p>
        )}

        {/* ALWAYS present — it is the priority key the whole epic subtracts
            from. The escalation is the SECOND text signal, and the one that says
            HOW late. */}
        <p
          className={cn("text-sm", ticket.overdue ? "font-semibold text-danger" : "text-ink")}
        >
          {isolateLtr(t("atelier.dueDate", { date }), date)}
        </p>

        <p className="text-sm text-ink-muted">
          {/* `bandLabel`'s «{{minutes}} דק׳» fallback is the visible consequence
              of "minutes persist, never the label": a boutique that re-tuned
              «חצי יום» leaves older tickets matching no live band, and the card
              must not silently re-value the garment. */}
          {bandLabel(ticket.effort_minutes, bands, t)}
          {" · "}
          {ticket.assigned_staff_user_id === null ? (
            t("atelier.unassigned")
          ) : seamstress !== undefined && seamstress.assignable ? (
            <bdi>{seamstress.display_name}</bdi>
          ) : (
            /* FROM THE WIRE'S `assignable` FLAG, never inferred from absence:
               F51's staff CRUD can re-role or retire a seamstress and knows
               nothing about this table, and surfacing it is the signal a manager
               needs to reassign. */
            t("atelier.assigneeInactive")
          )}
        </p>

        {/* ⚠ THE NOTE IS THE WORK ORDER, and «עריכה» is refused to a seamstress
            on a ticket that is not hers — so a clamp here would hide the
            instruction from precisely the person doing the work. `break-words`,
            never `line-clamp`. */}
        {ticket.notes !== null && (
          <p className="text-sm break-words text-ink">
            <bdi>{ticket.notes}</bdi>
          </p>
        )}

        {mayWork && later.length > 0 && (
          <div className="mt-3 space-y-2">
            {/* THE PRIMARY PATH: one control, one tap, one stage — the 90% case,
                first in the card's tab order and the same physical position on
                every card in every column. */}
            <Button
              data-control="advance"
              variant="secondary"
              size="md"
              fullWidthMobile={false}
              loading={busy}
              // A 30-card board otherwise exposes 30 controls all named «לשלב
              // הבא», and a screen-reader or speech-input user cannot address a
              // specific ticket (WCAG 4.1.2 / 2.4.6). The value STARTS with the
              // visible label so 2.5.3 label-in-name holds. No bidi treatment —
              // an aria-label takes no markup.
              aria-label={t("atelier.advanceAria", { name: ticket.customer_name })}
              onClick={() => onAdvance(ticket, later[0])}
            >
              {t("atelier.advance")}
            </Button>
          </div>
        )}
      </Card>
    </li>
  );
}
