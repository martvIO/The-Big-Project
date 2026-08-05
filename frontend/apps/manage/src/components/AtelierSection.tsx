import { useEffect, useRef, useState } from "react";
import {
  Badge,
  Button,
  Card,
  cn,
  DateField,
  EmptyState,
  focusRing,
  Input,
  Modal,
  Select,
  Skeleton,
  TextArea,
} from "@boutique/ui";
import { useTranslation } from "react-i18next";
import { api, ApiError } from "../api";
import type {
  AtelierBoardResponse,
  AtelierSettingsUpdate,
  AtelierTicket,
  EffortBand,
  EffortBandRef,
  SeamstressRef,
  TicketStage,
} from "../api";
import { SeamstressPanel } from "./SeamstressPanel";
import { isolateBidi, isolateLtr } from "../lib/booking";
import {
  hoursFromMinutes,
  loadMinutes,
  overloaded,
  remainingMinutes,
  sortByRemainingCapacity,
  wouldOverload,
} from "../lib/capacity";
import { jerusalemTime, plainDate, todayJerusalem } from "../lib/jerusalem";
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

// ⚠ NOTHING ON THIS BOARD MUTATES ON `change`, and this is the one interaction
// rule a builder gets wrong by copying the obvious thing. On Windows Chrome and
// Firefox a CLOSED native <select> changes its value and fires `change` on every
// arrow keypress, so an onChange-mutating skip would write three timestamps,
// three audit rows and three column moves while a keyboard user was still
// choosing — WCAG 3.2.2 On Input, Level A. Both selects set per-card DRAFT state
// and a sibling commit Button issues the request, which is also how every
// shipped <Select> in this console already works.
type Drafts = Record<string, string>;

// The client twin of `normalize_israeli_mobile`, same steps in the same order.
// ⚠ Deliberately NOT in validation.ts: that file is the one
// `test_frontend_constant_parity` scrapes for MIRRORED BOUNDS, and this mirrors
// an ALGORITHM rather than a number — the same reason `validateStaffDraft`'s
// email shape check lives outside it. No atelier BOUND is mirrored here at all:
// the due-date horizon and the label lengths are server bounds and the console
// renders the 400 they answer.
const PHONE_CHARSET = /^\+?[0-9 ()-]+$/;
const NORMALIZED_MOBILE = /^\+9725\d{8}$/;

function parsesAsMobile(raw: string): boolean {
  const candidate = raw.trim();
  if (candidate === "" || !PHONE_CHARSET.test(candidate)) {
    return false;
  }
  let digits = candidate.replace(/\D/g, "");
  if (digits.startsWith("05")) {
    digits = `972${digits.slice(1)}`;
  }
  return NORMALIZED_MOBILE.test(`+${digits}`);
}

// `TextArea showCount` needs it and the deck mandates it, which is what makes
// "the board never truncates a note" honest — the length is visible at the
// moment it is chosen rather than discovered on the board.
const NOTES_MAX = 500;

interface AtelierSectionProps {
  /** The signed-in staffer's id — the claim/release axis reads it. */
  selfId: string;
  /** Her role. Cosmetics only: the control is the server's D3/D9/D10 checks. */
  role: string;
}

interface FormState {
  mode: "create" | "edit";
  ticketId: string | null;
  customerName: string;
  customerPhone: string;
  dueDate: string;
  effortBand: EffortBand;
  dressName: string;
  dressSize: string;
  notes: string;
}

type FormField = "customerName" | "customerPhone" | "dueDate" | "notes";

function headingId(stage: TicketStage): string {
  return `atelier-h-${stage}`;
}

function orNull(value: string): string | null {
  const trimmed = value.trim();
  return trimmed === "" ? null : trimmed;
}

export function AtelierSection({ selfId, role }: AtelierSectionProps) {
  const { t } = useTranslation();

  const [boardData, setBoardData] = useState<AtelierBoardResponse | null>(null);
  // ⚠ HOW MANY PAYLOADS THIS RENDER HAS SEEN, and it is STATE on purpose — the
  // restore effect below is the only reader and it needs the number the commit
  // it belongs to was painted with, not the newest one. See `applyBoard`.
  const [boardCommit, setBoardCommit] = useState(0);
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
  // ticket id -> the `data-control` of the ONE control that is loading. A-busy
  // disables the tapped control and nothing else: one tap must not freeze the
  // board for the other staffer standing beside her.
  const [busy, setBusy] = useState<Drafts>({});
  const [cardError, setCardError] = useState<{ id: string; text: string } | null>(null);
  const [skipDrafts, setSkipDrafts] = useState<Drafts>({});
  const [assignDrafts, setAssignDrafts] = useState<Drafts>({});
  const [form, setForm] = useState<FormState | null>(null);
  const [formErrors, setFormErrors] = useState<Partial<Record<FormField, string>>>({});
  const [formAlert, setFormAlert] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [pendingDelete, setPendingDelete] = useState<AtelierTicket | null>(null);
  // §7.4 Refused. The delete confirm is the ONE write whose trigger lives in a
  // modal <dialog>, so the in-card alert every other write uses is painted
  // BEHIND the backdrop — inert, unfocusable and pruned from the a11y tree.
  // Its own alert, the form dialog's shape exactly.
  const [deleteAlert, setDeleteAlert] = useState<string | null>(null);

  const headingRef = useRef<HTMLHeadingElement>(null);
  const sectionRef = useRef<HTMLElement>(null);
  const terminalRef = useRef<HTMLParagraphElement>(null);
  // ⚠ C4 — ONE UNCONDITIONAL CAPTURE, five destinations. Recorded BEFORE an
  // incoming payload is applied (the only moment both lists exist) and before
  // every write, and consumed after the paint iff `document.activeElement` is
  // <body> — which is the browser saying the repaint dropped focus rather than
  // the user moving it. That guard is what makes «unconditional» free: if focus
  // is still on something real the restore does nothing, and it is strictly less
  // code than any predicate over the two lists.
  //
  // `capturedAt` is the `boardCommit` value current when the intent was
  // recorded. Every intent is recorded immediately before exactly ONE
  // `applyBoard` — `load` captures then applies, `runWrite` records then applies
  // — so «the repaint this intent is waiting for» is precisely «the first board
  // commit after `capturedAt`», and the effect can test for it rather than
  // guess from where focus happens to be.
  const restoreRef = useRef<{
    ticketId: string;
    control: string | null;
    columnStage: TicketStage;
    capturedAt: number;
  } | null>(null);
  const cardAlertRef = useRef<HTMLParagraphElement>(null);
  const formAlertRef = useRef<HTMLParagraphElement>(null);
  const deleteAlertRef = useRef<HTMLParagraphElement>(null);
  // `load` runs outside render and would otherwise close over a stale payload.
  const boardRef = useRef<AtelierBoardResponse | null>(null);
  // …and `boardCommit`'s state copy is one render behind by design, so the
  // capture sites — which also run outside render — read the count from here.
  const boardCommitRef = useRef(0);
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

  // ⚠ C7 — A TERMINAL DEFERS WHILE A DIALOG IS OPEN. Unmounting the section
  // under an open dialog would silently discard typed work, and a 401 arriving
  // mid-form is exactly the case: the session outlives a shift, so the realistic
  // reader is a phone left on a bench.
  // ⚠ C7 — AND THE PANEL'S TWO DIALOGS COUNT. They live inside SeamstressPanel
  // where this component cannot see them, so the panel reports its own state
  // upward; without it a 401 tick unmounts a settings dialog holding six edited
  // band values.
  const [panelDialogOpen, setPanelDialogOpen] = useState(false);
  const dialogOpen = form !== null || pendingDelete !== null || panelDialogOpen;

  // ⚠ A COUNTER, not the payload, and NOT `[boardData]` in a dependency array:
  // `setBoardData` BAILS OUT of a reference-identical payload, so keying the
  // restore on the data would silently skip the one repaint an intent is
  // waiting for. `setBoardCommit` always changes, so a board application always
  // produces a commit, and two applications collapsed into one render still
  // move the count past every intent they subsume.
  const applyBoard = (next: AtelierBoardResponse) => {
    boardRef.current = next;
    boardCommitRef.current += 1;
    setBoardData(next);
    setBoardCommit(boardCommitRef.current);
  };

  /**
   * Record where focus is, if it is inside a card. Unconditional: no comparison
   * against the incoming list, because the case that matters most has no stage
   * change at all — a seamstress tabbed onto «לקחת» whose colleague claims the
   * ticket gets a card with ZERO controls for her, in the same column, still in
   * the payload. Every predicate the deck proposed is false there.
   */
  const captureFocus = () => {
    restoreRef.current = null;
    const active = document.activeElement;
    if (!(active instanceof Element)) {
      return;
    }
    const ticketId = active.closest("[data-ticket-id]")?.getAttribute("data-ticket-id");
    if (ticketId === undefined || ticketId === null) {
      return;
    }
    const row = boardRef.current?.tickets.find((item) => item.id === ticketId);
    if (row === undefined) {
      return;
    }
    restoreRef.current = {
      ticketId,
      control: active.closest("[data-control]")?.getAttribute("data-control") ?? null,
      columnStage: row.stage,
      capturedAt: boardCommitRef.current,
    };
  };

  const load = async () => {
    const generation = poll.generation();
    try {
      const result = await api.getAtelierBoard();
      if (!poll.isCurrent(generation)) {
        return;
      }
      // Decided BEFORE the new list is applied — the only moment both lists
      // exist.
      captureFocus();
      applyBoard(result);
      // The freshness claim changes ONLY on a success, which is what makes it a
      // claim the board can keep.
      setUpdatedAt(new Date().toISOString());
      setStale(false);
      setLoadFailed(false);
      // The in-card alert promises «הלוח יתעדכן בעדכון הבא» and this is the
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

  useEffect(() => {
    // The deferred terminal takes focus when the dialog that held it back is
    // dismissed: native <dialog> focus-return targets a trigger the terminal
    // panel has just unmounted, so without this focus lands on <body>.
    if (terminal !== null && !dialogOpen) {
      terminalRef.current?.focus();
    }
  }, [terminal, dialogOpen]);

  useEffect(() => {
    // AFTER THE PAINT, and only if the repaint dropped focus. The order is the
    // one C4 fixes: (1) the same control on the same ticket, wherever it now is;
    // (2) any control on that ticket; (3) the NEW column's heading; (4) the
    // RECORDED column's heading, which is the delete case — the card is gone
    // entirely, so there is nothing to look up.
    //
    // Focusing the destination also scrolls it into view natively, so the
    // stacked layout needs no scroll code.
    const target = restoreRef.current;
    if (target === null) {
      return;
    }
    // ⚠ THE INTENT BELONGS TO ONE COMMIT AND EXPIRES ON IT. This effect is
    // queued after EVERY commit, so it also runs on commits whose DOM still
    // PREDATES the repaint the intent is waiting for: React flushes a commit's
    // passive effects in a task of its own, and a later render pass drains them
    // before it paints. Those passes carry the OLD `boardCommit` — the count the
    // intent was recorded at, or less — so they decline here and leave it alone.
    // Clearing above this line is what shipped the defect: a stale pass ate the
    // intent, its own precondition then failed, and the real repaint arrived
    // with nothing left to restore.
    if (boardCommit <= target.capturedAt) {
      return;
    }
    // Past it, so the repaint HAS landed. The intent dies here whatever happens
    // next, which is the half a `document.activeElement` test cannot supply:
    // «focus is still inside the captured card» is equally true of a repaint
    // that has not landed and of a user sitting still with nothing pending, and
    // an intent kept for the second case is a stolen focus later — the next
    // commit that finds her on <body>, for ANY reason including her own Tab out
    // of the document, hands her back to a card she left. Expiry is decided by
    // the payload, not by where she happens to be standing.
    restoreRef.current = null;
    if (document.activeElement !== document.body) {
      return;
    }
    const root = sectionRef.current;
    if (root === null) {
      return;
    }
    const card = Array.from(root.querySelectorAll("[data-ticket-id]")).find(
      (node) => node.getAttribute("data-ticket-id") === target.ticketId,
    );
    if (card !== undefined) {
      const same =
        target.control === null
          ? null
          : card.querySelector<HTMLElement>(`[data-control="${target.control}"]`);
      if (same !== null) {
        same.focus();
        return;
      }
      const any = card.querySelector<HTMLElement>("[data-control]");
      if (any !== null) {
        any.focus();
        return;
      }
    }
    const landed = boardRef.current?.tickets.find((item) => item.id === target.ticketId);
    const destination =
      (landed === undefined ? null : document.getElementById(headingId(landed.stage))) ??
      document.getElementById(headingId(target.columnStage));
    destination?.focus();
    // ⚠ NO DEPENDENCY ARRAY, deliberately. Keyed on [boardData] this effect
    // would SILENTLY NEVER FIRE for a poll that handed `setBoardData` a
    // reference-identical payload — React bails out of the update and the effect
    // is skipped, which is the defect FloorPanel records in its own words for
    // its [cards] effect. `boardCommit` above is what makes that moot: it is
    // read from the render, so every commit is judged on its own count and the
    // ones with nothing to do return on the first line. Anyone adding an array
    // here must key it on [boardCommit] and never on [boardData].
  });

  useEffect(() => {
    // A refused write moves focus to the in-card alert. Keyed on the error state
    // rather than raised inside the handler, because the alert node does not
    // exist yet when setCardError runs. THE FAILURE PATH IS THE ONE THAT GETS
    // FORGOTTEN — this bug class has shipped three times in this repo and axe
    // walked past it every time, because axe cannot see a focus move that never
    // happened.
    if (cardError !== null) {
      cardAlertRef.current?.focus();
    }
  }, [cardError]);

  useEffect(() => {
    // The dialog's own alert, same rule. Never a Toast behind a modal, and never
    // a message the dialog dismisses itself to show.
    if (formAlert !== null) {
      formAlertRef.current?.focus();
    }
  }, [formAlert]);

  useEffect(() => {
    // And the delete dialog's, same rule again. Without this the refusal leaves
    // focus on a re-enabled «מחיקה» that will keep answering 404.
    if (deleteAlert !== null) {
      deleteAlertRef.current?.focus();
    }
  }, [deleteAlert]);

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
   * The mutation envelope every write shares: the loop issues no tick while one
   * is in flight, so a card cannot be repainted underneath its own request, and
   * the bump discards the one poll that could still be in the air.
   *
   * `poll.fail` is what makes a write's 403 TERMINAL on the same {401,403} rule
   * the ticks use. A 404 is NOT terminal — a ticket vanishing is a fact about
   * the ticket, not about her access.
   */
  const runMutation = async <T,>(
    send: () => Promise<T>,
    // ⚠ F42's TWO PANEL WRITES PASS `false`, and the reason is not shared with
    // any F41 write. `poll.fail`'s {401,403} rule reads a 403 as «her access to
    // THIS BOARD has ended» — true of every write above, whose gate is the
    // router's own three roles. The capacity route and PUT /manage/settings
    // carry PER-ROUTE tightenings to owner + shift_manager, so their 403 means
    // «not this control», and blanking a board she may still READ would be the
    // console punishing her for a button it offered her. A 401 is still the
    // session, and the next tick (≤5 s) classifies it through the shipped rule
    // rather than through a second classifier here.
    terminalOnFailure = true,
  ): Promise<{ ok: true; value: T } | { ok: false; error: unknown }> => {
    mutationsRef.current += 1;
    poll.clearTick();
    poll.bump();
    try {
      return { ok: true, value: await send() };
    } catch (error) {
      if (terminalOnFailure) {
        poll.fail(error);
      }
      return { ok: false, error };
    } finally {
      mutationsRef.current -= 1;
      // THE RE-ARM, in the .finally() rather than the success path: a refused
      // write must not park the loop either, or the board silently stops
      // converging the first time anybody acts.
      if (mutationsRef.current === 0) {
        poll.reschedule();
      }
    }
  };

  /**
   * ⚠ C5 — THE `default:` BRANCH IS STRUCTURAL, NOT COSMETIC. `main.py`'s error
   * bodies are ENGLISH and this console is Hebrew-only, so falling through to
   * `errorMessage(error)` would put an English sentence in a Hebrew board the
   * first time any code F41 did not anticipate is raised.
   */
  const cardErrorText = (error: unknown): string => {
    if (error instanceof ApiError) {
      switch (error.code) {
        case "TICKET_STAGE_CONFLICT":
          return t("atelier.error.stageConflict");
        case "TICKET_ALREADY_ASSIGNED":
          return t("atelier.error.alreadyAssigned");
        case "NOT_FOUND":
          return t("atelier.error.notFound");
      }
    }
    return t("atelier.error.rejected");
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
    control: string,
    send: () => Promise<AtelierTicket | null>,
    cueOf: (patched: AtelierTicket | null) => { text: string; name: string | null },
    // Where a refusal is RENDERED. Omitted means the in-card alert; the delete
    // confirm passes its dialog's own, because a message painted behind an open
    // modal is a message nobody can read or hear.
    onError?: (text: string) => void,
  ): Promise<boolean> => {
    setBusy((current) => ({ ...current, [ticket.id]: control }));
    setCardError(null);
    const result = await runMutation(send);
    setBusy((current) => {
      const next = { ...current };
      delete next[ticket.id];
      return next;
    });
    if (!result.ok) {
      const text = cardErrorText(result.error);
      if (onError === undefined) {
        setCardError({ id: ticket.id, text });
      } else {
        onError(text);
      }
      return false;
    }
    const patched = result.value;
    const current = boardRef.current;
    if (current !== null) {
      // Recorded EXPLICITLY rather than read off `document.activeElement`, and
      // at the same moment `load` records — immediately before the new list is
      // applied. The delete's confirm button lives in a DIALOG and not in a
      // card, so the unconditional capture would find nothing on the one act
      // that most needs a destination; and the tapped control is `disabled`
      // while the request is in flight, which real browsers blur.
      restoreRef.current = {
        ticketId: ticket.id,
        control,
        columnStage: ticket.stage,
        capturedAt: boardCommitRef.current,
      };
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
  };

  const stageCue = (key: string, patched: AtelierTicket | null, fallback: TicketStage) => ({
    text: t(key, {
      name: patched?.customer_name ?? "",
      stage: t(STAGE_LABEL_KEY[patched?.stage ?? fallback]),
    }),
    name: patched?.customer_name ?? null,
  });

  const advance = (ticket: AtelierTicket, stage: TicketStage, control: string) => {
    void runWrite(ticket, control, () => api.advanceStage(ticket.id, stage), (patched) => {
      setSkipDrafts((current) => ({ ...current, [ticket.id]: "" }));
      return stageCue("atelier.cue.advanced", patched, stage);
    });
  };

  // Undo CLEARS the ticket's CURRENT stamp — the rightmost one — and the audit
  // row carries the timestamp it destroyed, which is the only surviving copy.
  const undo = (ticket: AtelierTicket) => {
    void runWrite(
      ticket,
      "undo",
      () => api.undoStage(ticket.id, ticket.stage),
      (patched) => stageCue("atelier.cue.undone", patched, ticket.stage),
    );
  };

  const assign = (ticket: AtelierTicket, staffUserId: string | null, control: string) => {
    void runWrite(ticket, control, () => api.assignTicket(ticket.id, staffUserId), () => {
      setAssignDrafts((current) => {
        const next = { ...current };
        delete next[ticket.id];
        return next;
      });
      if (staffUserId === null) {
        // No interpolation at all: the card did not move, focus is still on it,
        // and there is no new value to name.
        return { text: t("atelier.cue.released"), name: null };
      }
      // ⚠ ONE interpolated USER value, never two: the card does not move on an
      // assign, so focus is the referent and the ticket is already named. Two
      // names in one string is what the shipped `isolateBidi(text, value)`
      // cannot isolate without inventing a second helper.
      const held = boardRef.current;
      const target = held?.seamstresses.find((row) => row.id === staffUserId);
      const seamstress = target?.display_name ?? "";
      // ⚠ F41's D17 forbids the poll from writing into the announced region, so
      // a sighted user watches the bar turn red on the next tick and a
      // screen-reader user gets NOTHING AT ALL unless the cue says it — which
      // would make overload a SIGHTED-ONLY signal on the one action that causes
      // it, on a screen where a11y is a legal bar.
      //
      // ⚠ GATED ON AN ACTUAL MOVE. `due_soon_minutes` is her PRE-WRITE load and
      // already includes anything she holds; the commit fires whenever a draft
      // exists and the Select's value defaults to the current assignee, so
      // arrowing away and back and committing sends a NO-OP assign to the
      // current holder. Ungated, the console would add minutes it has already
      // counted and announce a false overload with no colleague and no race.
      //
      // ⚠ AND IT IS `loadMinutes` AND NOT `ticket.effort_minutes`. The sum
      // `wouldOverload` adds to is `SUM(...) FILTER (WHERE due_date <=
      // horizon)`, so a ticket due after `due_soon_through` — the normal case,
      // since assignment happens at intake and the wedding is weeks out —
      // contributes NOTHING to it. Unfiltered, this cue announces «עומס יתר»
      // for minutes the server will never count, and every rendered surface
      // then contradicts it: the bar stays gold, `Row`'s sentence carries no
      // word, and D17 forbids the poll from retracting what was announced.
      //
      // ⚠ And it is `wouldOverload`/`loadMinutes` and nothing else — NO
      // arithmetic, no `60` and no date compare at this call site. A
      // hand-rolled predicate that dropped the null guard computes
      // `null * 60 = 0` in JS and announces «עומס יתר» on EVERY assign to an
      // unconfigured seamstress: correct on screen, green under axe, and a
      // legal-accessibility regression on the one channel a screen-reader user
      // has.
      const over =
        held !== null &&
        target !== undefined &&
        ticket.assigned_staff_user_id !== staffUserId &&
        wouldOverload(target, loadMinutes(ticket, held.due_soon_through));
      return {
        text: t(over ? "atelier.cue.assignedOverload" : "atelier.cue.assigned", { seamstress }),
        name: seamstress,
      };
    });
  };

  /**
   * ⚠ THE ANSWER IS CAPACITY FACTS ONLY, AND ONLY THREE KEYS ARE PATCHED. The
   * write has no load aggregate — buying one would be a second business
   * statement on a write — so the only pair it could carry is `(0, 0)`, which
   * would COLLAPSE HER BAR AND DROP HER «עומס יתר» WORD for up to five seconds
   * on this feature's own primary surface, at the moment a manager is looking
   * at it. `assigned_minutes` and `due_soon_minutes` keep their last-tick
   * values and the next tick replaces the envelope whole.
   */
  const saveCapacity = async (staffUserId: string, hours: number | null): Promise<boolean> => {
    const result = await runMutation(
      () => api.setSeamstressCapacity(staffUserId, hours),
      false,
    );
    if (!result.ok) {
      return false;
    }
    const patched = result.value;
    const held = boardRef.current;
    if (held !== null) {
      applyBoard({
        ...held,
        seamstresses: held.seamstresses.map((row) =>
          row.id === patched.id
            ? {
                ...row,
                assignable: patched.assignable,
                weekly_capacity_hours: patched.weekly_capacity_hours,
                capacity_is_default: patched.capacity_is_default,
              }
            : row,
        ),
      });
    }
    // Keyed on what SHE DID, not on what came back: «חזרה לברירת המחדל» is the
    // act, and the server's answer is the same resolved number either way.
    setCue({
      text: t(hours === null ? "atelier.capacity.cue.cleared" : "atelier.capacity.cue.saved", {
        name: patched.display_name,
      }),
      name: patched.display_name,
    });
    return true;
  };

  /**
   * ⚠ NOTHING IS PATCHED FROM THIS RESPONSE (C7, accepted). `effort_bands` and
   * `default_weekly_capacity_hours` are ENVELOPE fields the poll owns, and
   * patching them from a different endpoint's answer would put a second writer
   * on data the board is authoritative for. So for up to one tick every
   * rendered default and every `bandLabel` is the previous mapping's — bounded,
   * self-correcting, with no user action, and the dialog's own cue has already
   * told her the write landed.
   */
  const saveAtelierSettings = async (patch: AtelierSettingsUpdate): Promise<boolean> => {
    const result = await runMutation(() => api.updateSettings({ atelier: patch }), false);
    if (!result.ok) {
      return false;
    }
    setCue({ text: t("atelier.settings.cue.saved"), name: null });
    return true;
  };

  const confirmDelete = (ticket: AtelierTicket) => {
    void runWrite(
      ticket,
      "delete",
      () => api.deleteTicket(ticket.id).then(() => null),
      () => {
        // ⚠ CLOSED HERE, inside `cueOf`, and not from a `.then()` on the write:
        // it has to land in the SAME commit as the card's removal. A later batch
        // closes the <dialog> AFTER the restore effect has already focused the
        // column heading, and the dialog's own focus-return then drops focus to
        // <body> — an intermittently green test over a permanently stranded
        // user. Clearing a draft inside `cueOf` is the shape the skip and assign
        // writes already use.
        setPendingDelete(null);
        return {
          text: t("atelier.cue.deleted", { name: ticket.customer_name }),
          name: ticket.customer_name,
        };
      },
      setDeleteAlert,
    );
  };

  const openCreate = () => {
    setFormErrors({});
    setFormAlert(null);
    setForm({
      mode: "create",
      ticketId: null,
      customerName: "",
      customerPhone: "",
      // ⚠ EMPTY, never today: a due date is the one field a hurried user must
      // not be able to accept by not looking at it.
      dueDate: "",
      // The middle-low band. `full_day` inflates every estimate in the boutique
      // and `thirty_min` deflates it.
      effortBand: "one_hour",
      dressName: "",
      dressSize: "",
      notes: "",
    });
  };

  const openEdit = (ticket: AtelierTicket) => {
    setFormErrors({});
    setFormAlert(null);
    setForm({
      mode: "edit",
      ticketId: ticket.id,
      customerName: ticket.customer_name,
      customerPhone: "",
      dueDate: ticket.due_date,
      // A ticket whose stored minutes match no live band necessarily re-values
      // on save: `UpdateTicketRequest` takes a band KEY and never minutes, so
      // there is no shape in which the old number survives an edit.
      effortBand:
        boardRef.current?.effort_bands.find((band) => band.minutes === ticket.effort_minutes)
          ?.band ?? "one_hour",
      dressName: ticket.dress_name ?? "",
      dressSize: ticket.dress_size ?? "",
      notes: ticket.notes ?? "",
    });
  };

  const submitForm = async () => {
    if (form === null) {
      return;
    }
    // Client-side for SHAPE, server-side for TRUTH — and exactly the four the
    // spec names. No LENGTH bound is restated here: those are server bounds and
    // the console renders the 400 they answer.
    const errors: Partial<Record<FormField, string>> = {};
    if (form.mode === "create") {
      if (form.customerName.trim() === "") {
        errors.customerName = t("atelier.form.error.customerName");
      }
      if (!parsesAsMobile(form.customerPhone)) {
        errors.customerPhone = t("atelier.form.error.customerPhone");
      }
    }
    if (form.dueDate === "") {
      errors.dueDate = t("atelier.form.error.dueDate");
    }
    if (form.notes.length > NOTES_MAX) {
      errors.notes = t("atelier.form.error.notes");
    }
    setFormErrors(errors);
    if (Object.keys(errors).length > 0) {
      return;
    }

    setSubmitting(true);
    setFormAlert(null);
    const ticketId = form.ticketId;
    const result = await runMutation(() =>
      form.mode === "create"
        ? api.createTicket({
            customer_name: form.customerName.trim(),
            customer_phone: form.customerPhone.trim(),
            due_date: form.dueDate,
            effort_band: form.effortBand,
            assigned_staff_user_id: null,
            dress_id: null,
            dress_name: orNull(form.dressName),
            dress_size: orNull(form.dressSize),
            notes: orNull(form.notes),
          })
        : api.updateTicket(ticketId ?? "", {
            // ⚠ A FULL REPLACE, every editable field: with optional fields an
            // omitted key and an explicitly cleared one are the same request, so
            // a console that forgot `notes` would silently delete a bride's
            // measurements.
            due_date: form.dueDate,
            effort_band: form.effortBand,
            dress_id: null,
            dress_name: orNull(form.dressName),
            dress_size: orNull(form.dressSize),
            notes: orNull(form.notes),
          }),
    );
    setSubmitting(false);
    if (!result.ok) {
      setFormAlert(t("atelier.form.error.server"));
      return;
    }

    const saved = result.value;
    const current = boardRef.current;
    if (current !== null) {
      applyBoard({
        ...current,
        tickets:
          form.mode === "create"
            ? // Appended rather than inserted by `due_date`: order is the
              // SERVER's and the client never re-sorts. The next tick, at most
              // five seconds away, puts it in its place.
              [...current.tickets, saved]
            : current.tickets.map((row) => (row.id === saved.id ? saved : row)),
      });
    }
    setUpdatedAt(new Date().toISOString());
    // ⚠ OUTSIDE the mode branch, and it was inside it: the edit path announced
    // NOTHING on a successful 200. Both cues name the bride — create because
    // native <dialog> returns focus to «כרטיס חדש» and NOT to the new card, so
    // nothing else says which ticket was opened; update because an edit replaces
    // five fields at once and has no single new value to name in its place.
    setCue({
      text: t(form.mode === "create" ? "atelier.cue.created" : "atelier.cue.updated", {
        name: saved.customer_name,
      }),
      name: saved.customer_name,
    });
    setForm(null);
  };

  const heading = (
    <h2 ref={headingRef} tabIndex={-1} className="text-lg font-semibold text-ink">
      {t("atelier.heading")}
    </h2>
  );

  if (terminal !== null && !dialogOpen) {
    // The board is over. Cards are cleared: a dead session cannot vouch for
    // them, and on the 403 the board is exactly what she may no longer see.
    return (
      <section className="space-y-6">
        {heading}
        <p ref={terminalRef} role="alert" tabIndex={-1} className="text-sm text-ink">
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

  const intakeCta = (
    <Button variant="primary" size="md" fullWidthMobile={false} onClick={openCreate}>
      {t("atelier.newTicket")}
    </Button>
  );

  // ⚠ SORTED ONCE, HERE, and read by BOTH render sites — the panel's <ul> and
  // every card's assign <Select>. A per-card sort would run it sixty times a
  // paint on a five-second poll. Sorted on the CLIENT and never in the SQL:
  // `remaining` is a pure function of two fields already on the wire, so a
  // server sort would be a second ordering to keep in step and would reorder
  // the payload for every other consumer. A NEW array, so the held envelope
  // keeps the server's own `display_name, id` order.
  const seamstresses = sortByRemainingCapacity(boardData?.seamstresses ?? []);

  return (
    <section ref={sectionRef} className="space-y-4">
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

      {/* ⚠ ONE CONDITIONAL, ABOVE ALL FOUR BOARD BRANCHES AND BELOW THE CUE.
          The zero-ticket branch replaces both the columns AND the rail, so a
          panel rendered only beside the columns would be invisible on exactly
          the screen a brand-new boutique opens on — where setting capacity
          before the first intake is the useful order. It gates on the ENVELOPE
          and not on the tickets: with no payload there is no denominator, no
          horizon and no roster, and four empty strings claiming to be a panel
          is worse than no panel. */}
      {boardData !== null && (
        <SeamstressPanel
          seamstresses={seamstresses}
          unassignedMinutes={boardData.unassigned_minutes}
          dueSoonThrough={boardData.due_soon_through}
          role={role}
          defaultCapacityHours={boardData.default_weekly_capacity_hours}
          bands={boardData.effort_bands}
          onSaveCapacity={saveCapacity}
          onSaveAtelierSettings={saveAtelierSettings}
          onDialogOpenChange={setPanelDialogOpen}
        />
      )}

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
          action={intakeCta}
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

          <div>{intakeCta}</div>

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
              <section key={stage} aria-labelledby={headingId(stage)} className="space-y-2">
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
                      seamstresses={seamstresses}
                      busyControl={busy[ticket.id] ?? null}
                      alert={cardError?.id === ticket.id ? cardError.text : null}
                      alertRef={cardAlertRef}
                      role={role}
                      selfId={selfId}
                      skipDraft={skipDrafts[ticket.id] ?? ""}
                      assignDraft={assignDrafts[ticket.id]}
                      onSkipDraft={(value) =>
                        setSkipDrafts((current) => ({ ...current, [ticket.id]: value }))
                      }
                      onAssignDraft={(value) =>
                        setAssignDrafts((current) => ({ ...current, [ticket.id]: value }))
                      }
                      onAdvance={advance}
                      onUndo={undo}
                      onAssign={assign}
                      onEdit={openEdit}
                      onDelete={(row) => {
                        setDeleteAlert(null);
                        setPendingDelete(row);
                      }}
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

      {/* ⚠ C6 — BOTH DIALOGS MOUNT AT SECTION LEVEL, siblings of the column
          grid, with their open state and draft in this component's state keyed
          by ticket id. Inside an <li> a repaint that moved or removed the card
          would unmount the dialog and discard what she typed. */}
      <Modal
        open={form !== null}
        onClose={() => setForm(null)}
        title={t(form?.mode === "edit" ? "atelier.form.editTitle" : "atelier.newTicket")}
        footer={
          <>
            <Button
              type="button"
              variant="ghost"
              size="md"
              fullWidthMobile={false}
              onClick={() => setForm(null)}
            >
              {t("atelier.form.cancel")}
            </Button>
            <Button
              type="button"
              variant="primary"
              size="md"
              fullWidthMobile={false}
              loading={submitting}
              onClick={() => void submitForm()}
            >
              {t(form?.mode === "edit" ? "atelier.form.submitEdit" : "atelier.form.submitCreate")}
            </Button>
          </>
        }
      >
        {form !== null && (
          <div className="space-y-3 text-start">
            {form.mode === "create" ? (
              <>
                <Input
                  label={t("atelier.form.customerName")}
                  value={form.customerName}
                  error={formErrors.customerName}
                  onChange={(event) =>
                    setForm({ ...form, customerName: event.target.value })
                  }
                />
                <Input
                  label={t("atelier.form.customerPhone")}
                  type="tel"
                  inputMode="tel"
                  dir="ltr"
                  value={form.customerPhone}
                  error={formErrors.customerPhone}
                  onChange={(event) =>
                    setForm({ ...form, customerPhone: event.target.value })
                  }
                />
              </>
            ) : (
              /* A ticket opened for the wrong bride is a DELETE and a re-open,
                 not an edit that silently re-points a garment at someone else —
                 so the customer is a static line and the wire has no field for
                 her at all. */
              <p className="text-sm text-ink">
                <bdi>{form.customerName}</bdi>
              </p>
            )}

            {/* The platform feature, no picker library. NO `min` attribute: a
                past date is a 200 on the server and a WARNING here, because a
                dress that was due yesterday is exactly the ticket a boutique
                most needs to open — and a form that refuses it sends the
                seamstress to WhatsApp. */}
            <DateField
              label={t("atelier.form.dueDate")}
              value={form.dueDate}
              error={formErrors.dueDate}
              onChange={(event) => setForm({ ...form, dueDate: event.target.value })}
            />
            {form.dueDate !== "" && form.dueDate < todayJerusalem() && (
              <p className="text-sm text-warning-text">{t("atelier.form.pastDue")}</p>
            )}

            {/* ⚠ The option label carries the WORD AND its tenant-resolved
                MINUTES. F41 ships no editor for the mapping and F42 owns it, so
                showing the number at the moment the estimate is made is what
                lets an owner discover on day one that the platform thinks her
                half-day is four hours. An <option> takes no markup, so no
                isolation helper is available — the numeric run is bracketed by
                Hebrew on both sides instead. */}
            <Select
              label={t("atelier.form.effortBand")}
              className="min-h-11"
              value={form.effortBand}
              onChange={(event) =>
                setForm({ ...form, effortBand: event.target.value as EffortBand })
              }
            >
              {(boardData?.effort_bands ?? []).map((band) => (
                <option key={band.band} value={band.band}>
                  {t("atelier.bandOption", {
                    band: bandLabel(band.minutes, boardData?.effort_bands ?? [], t),
                    minutes: band.minutes,
                  })}
                </option>
              ))}
            </Select>

            {/* ⚠ C3 — THERE IS NO CATALOG DRESS Select, and the free-text field
                ships alone and unconditionally for all three roles. The only
                data source is GET /manage/dresses, gated owner + shift_manager
                while this dialog admits a seamstress, and F41 renders no dress
                image — so `dress_id` has no reader on this surface and is `null`
                on every request. F43 is the caller that will send an id. */}
            <Input
              label={t("atelier.form.dressName")}
              value={form.dressName}
              onChange={(event) => setForm({ ...form, dressName: event.target.value })}
            />
            <Input
              label={t("atelier.form.dressSize")}
              value={form.dressSize}
              onChange={(event) => setForm({ ...form, dressSize: event.target.value })}
            />
            <TextArea
              label={t("atelier.form.notes")}
              help={t("atelier.form.notesHelp")}
              showCount
              maxLength={NOTES_MAX}
              value={form.notes}
              error={formErrors.notes}
              onChange={(event) => setForm({ ...form, notes: event.target.value })}
            />

            {formAlert !== null && (
              /* ⚠ ONE alert INSIDE the dialog, above the footer — never a Toast
                 behind a modal and never a message the dialog dismisses itself
                 to show. This is where the horizon 400 and any code the console
                 did not anticipate land. */
              <p ref={formAlertRef} role="alert" tabIndex={-1} className="text-sm text-danger">
                {formAlert}
              </p>
            )}
          </div>
        )}
      </Modal>

      <Modal
        open={pendingDelete !== null}
        onClose={() => {
          setDeleteAlert(null);
          setPendingDelete(null);
        }}
        title={t("atelier.deleteConfirmTitle")}
        footer={
          <>
            <Button
              type="button"
              variant="ghost"
              size="md"
              fullWidthMobile={false}
              onClick={() => {
                setDeleteAlert(null);
                setPendingDelete(null);
              }}
            >
              {t("atelier.form.cancel")}
            </Button>
            <Button
              type="button"
              variant="danger"
              size="md"
              fullWidthMobile={false}
              loading={pendingDelete !== null && busy[pendingDelete.id] === "delete"}
              onClick={() => {
                if (pendingDelete !== null) {
                  confirmDelete(pendingDelete);
                }
              }}
            >
              {t("atelier.delete")}
            </Button>
          </>
        }
      >
        {/* Two sentences, and the second is the whole reason this dialog exists:
            there is no un-delete, so a ticket removed by mistake is recoverable
            only through psql. */}
        <p className="text-sm text-ink">
          {isolateBidi(
            t("atelier.deleteConfirmBody", { name: pendingDelete?.customer_name ?? "" }),
            pendingDelete?.customer_name ?? "",
          )}
        </p>
        {deleteAlert !== null && (
          <p ref={deleteAlertRef} role="alert" tabIndex={-1} className="mt-3 text-sm text-danger">
            {deleteAlert}
          </p>
        )}
      </Modal>
    </section>
  );
}

type Translate = (key: string, options?: Record<string, unknown>) => string;

/**
 * The half of an assign option that says WHY it is where it is in the list.
 *
 * ⚠ EVERY PART IS A KEY, INCLUDING THE « · » SEPARATOR, which is `optionRow`'s
 * own interpolation. F41 renders `{row.display_name}` alone here and declares no
 * key of this shape, so all three strings would otherwise ship as BARE HEBREW
 * LITERALS IN TSX — outside the `ar` parity guard, outside `HE_F41`'s prefix
 * fold, and invisible to the acceptance line for `atelier.capacity.*`.
 *
 * ⚠ An `<option>` takes no markup, so `isolateLtr` type-errors here and
 * `dir="ltr"` would REVERSE a Hebrew name. All three are safe by construction
 * instead: each ENDS in a Hebrew word, so no numeral ever lands at a paragraph
 * edge — «רותי · 4» is the shape that breaks and none of these is it.
 */
function assignDetail(row: SeamstressRef, t: Translate): string {
  const remaining = remainingMinutes(row);
  if (remaining === null) {
    return t("atelier.capacity.optionAssigned", {
      hours: hoursFromMinutes(row.assigned_minutes),
    });
  }
  if (overloaded(row)) {
    return t("atelier.capacity.over");
  }
  return t("atelier.capacity.optionRemaining", { hours: hoursFromMinutes(remaining) });
}

interface TicketCardProps {
  ticket: AtelierTicket;
  bands: readonly EffortBandRef[];
  seamstresses: readonly SeamstressRef[];
  busyControl: string | null;
  alert: string | null;
  alertRef: React.RefObject<HTMLParagraphElement | null>;
  role: string;
  selfId: string;
  skipDraft: string;
  assignDraft: string | undefined;
  onSkipDraft: (value: string) => void;
  onAssignDraft: (value: string) => void;
  onAdvance: (ticket: AtelierTicket, stage: TicketStage, control: string) => void;
  onUndo: (ticket: AtelierTicket) => void;
  onAssign: (ticket: AtelierTicket, staffUserId: string | null, control: string) => void;
  onEdit: (ticket: AtelierTicket) => void;
  onDelete: (ticket: AtelierTicket) => void;
  t: Translate;
}

function TicketCard({
  ticket,
  bands,
  seamstresses,
  busyControl,
  alert,
  alertRef,
  role,
  selfId,
  skipDraft,
  assignDraft,
  onSkipDraft,
  onAssignDraft,
  onAdvance,
  onUndo,
  onAssign,
  onEdit,
  onDelete,
  t,
}: TicketCardProps) {
  const later = laterStages(ticket.stage);
  const elevated = ELEVATED.has(role);
  const isSeamstress = role === "seamstress";
  const mine = ticket.assigned_staff_user_id === selfId;
  const unassigned = ticket.assigned_staff_user_id === null;
  // Which control EXISTS is COSMETICS and is asserted as cosmetics — the
  // server's D3/D9/D10 checks are the control. A seamstress may work her own
  // ticket or an unassigned one; on a colleague's she sees the facts and NO
  // CONTROLS AT ALL. Not a disabled button, not a lock glyph, not an «אין לך
  // הרשאה» line: a disabled control with no explanation is worse than an absent
  // one, an explanation would teach the permission model on a screen she opens
  // fifty times a shift, and either would be the client asserting a rule the
  // server owns.
  const mayWork = elevated || (isSeamstress && (mine || unassigned));
  const mayEdit = elevated || (isSeamstress && mine);
  const name = ticket.customer_name;
  const seamstress = seamstresses.find((row) => row.id === ticket.assigned_staff_user_id);
  const dressSize = ticket.dress_size;
  const date = plainDate(ticket.due_date);
  const controls =
    (mayWork && later.length > 0) ||
    (mayWork && ticket.stage !== "intake") ||
    elevated ||
    (isSeamstress && (unassigned || mine));

  return (
    <li data-ticket-id={ticket.id}>
      <Card className="space-y-1">
        <div className="flex flex-wrap items-center gap-2">
          {/* Bare <bdi>, never dir="ltr": forcing LTR on «מיכל לוי» reverses its
              words. NO truncation, clipping, ellipsis or line-clamp anywhere on
              this card — a board that abbreviates two garments into the same
              string is worse than a tall card, and the same argument holds for a
              person. */}
          <bdi className="font-semibold break-words text-ink">{name}</bdi>
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
        <p className={cn("text-sm", ticket.overdue ? "font-semibold text-danger" : "text-ink")}>
          {isolateLtr(t("atelier.dueDate", { date }), date)}
        </p>

        <p className="text-sm text-ink-muted">
          {/* `bandLabel`'s «{{minutes}} דק׳» fallback is the visible consequence
              of "minutes persist, never the label": a boutique that re-tuned
              «חצי יום» leaves older tickets matching no live band, and the card
              must not silently re-value the garment. */}
          {bandLabel(ticket.effort_minutes, bands, t)}
          {" · "}
          {unassigned ? (
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

        {controls && (
          /* §2.1's `--space-3` separation from the text block, and nothing else:
             no divider, no second Card. */
          <div className="mt-3 space-y-2">
            {mayWork && later.length > 0 && (
              /* THE PRIMARY PATH: one control, one tap, one stage — the 90%
                 case, first in the card's tab order and the same physical
                 position on every card in every column. */
              <div>
                <Button
                  data-control="advance"
                  variant="secondary"
                  size="md"
                  fullWidthMobile={false}
                  loading={busyControl === "advance"}
                  // A 30-card board otherwise exposes 30 controls all named
                  // «לשלב הבא», and a screen-reader or speech-input user cannot
                  // address a specific ticket (WCAG 4.1.2 / 2.4.6). The value
                  // STARTS with the visible label so 2.5.3 label-in-name holds.
                  // No bidi treatment — an aria-label takes no markup.
                  aria-label={t("atelier.advanceAria", { name })}
                  onClick={() => onAdvance(ticket, later[0], "advance")}
                >
                  {t("atelier.advance")}
                </Button>
              </div>
            )}

            {/* Rendered only when TWO OR MORE later stages exist: with exactly
                one it does what «לשלב הבא» already does, and a board that offers
                one act twice has to be read twice. */}
            {mayWork && later.length >= 2 && (
              <div className="flex flex-wrap items-end gap-2">
                <Select
                  data-control="skip"
                  label={t("atelier.skip")}
                  aria-label={t("atelier.skipAria", { name })}
                  className="min-h-11"
                  value={skipDraft}
                  onChange={(event) => onSkipDraft(event.target.value)}
                >
                  {/* The unchosen baseline. The skip Select has no «current»
                      option to sit on — a backwards option is never rendered —
                      so the prompt reuses the control's own visible label rather
                      than inventing a string, and the draft is genuinely null
                      until she picks. */}
                  <option value="">{t("atelier.skip")}</option>
                  {later.map((stage) => (
                    <option key={stage} value={stage}>
                      {t(STAGE_LABEL_KEY[stage])}
                    </option>
                  ))}
                </Select>
                <Button
                  data-control="skipCommit"
                  variant="secondary"
                  size="md"
                  fullWidthMobile={false}
                  disabled={skipDraft === ""}
                  loading={busyControl === "skipCommit"}
                  aria-label={t("atelier.skipCommitAria", { name })}
                  onClick={() => onAdvance(ticket, skipDraft as TicketStage, "skipCommit")}
                >
                  {t("atelier.skipCommit")}
                </Button>
              </div>
            )}

            {elevated && (
              <div className="flex flex-wrap items-end gap-2">
                {/* ⚠ The Select names WHAT IS BEING CHOSEN («תופרת») against the
                    Button's ACT («שיוך»): two controls in one card carrying the
                    same accessible name is WCAG 4.1.2, and no « — {{name}}»
                    suffix fixes it because both would carry it. */}
                <Select
                  data-control="assign"
                  label={t("atelier.assignLabel")}
                  aria-label={t("atelier.assignAria", { name })}
                  className="min-h-11"
                  value={assignDraft ?? ticket.assigned_staff_user_id ?? ""}
                  onChange={(event) => onAssignDraft(event.target.value)}
                >
                  <option value="">{t("atelier.unassigned")}</option>
                  {seamstresses
                    .filter((row) => row.assignable)
                    .map((row) => (
                      <option key={row.id} value={row.id}>
                        {t("atelier.capacity.optionRow", {
                          name: row.display_name,
                          detail: assignDetail(row, t),
                        })}
                      </option>
                    ))}
                </Select>
                <Button
                  data-control="assignCommit"
                  variant="secondary"
                  size="md"
                  fullWidthMobile={false}
                  disabled={assignDraft === undefined}
                  loading={busyControl === "assignCommit"}
                  aria-label={t("atelier.assignCommitAria", { name })}
                  onClick={() =>
                    onAssign(ticket, assignDraft === "" ? null : (assignDraft ?? null), "assignCommit")
                  }
                >
                  {t("atelier.assignCommit")}
                </Button>
              </div>
            )}

            {/* A seamstress's own pair: she takes it, or she gives it back. On a
                colleague's ticket she gets neither. */}
            {isSeamstress && unassigned && (
              <div>
                <Button
                  data-control="claim"
                  variant="secondary"
                  size="md"
                  fullWidthMobile={false}
                  loading={busyControl === "claim"}
                  aria-label={t("atelier.claimAria", { name })}
                  onClick={() => onAssign(ticket, selfId, "claim")}
                >
                  {t("atelier.claim")}
                </Button>
              </div>
            )}
            {isSeamstress && mine && (
              <div>
                <Button
                  data-control="release"
                  variant="ghost"
                  size="md"
                  fullWidthMobile={false}
                  loading={busyControl === "release"}
                  aria-label={t("atelier.releaseAria", { name })}
                  onClick={() => onAssign(ticket, null, "release")}
                >
                  {t("atelier.release")}
                </Button>
              </div>
            )}

            <div className="flex flex-wrap gap-2">
              {/* «ביטול שלב» cancels A STAGE, not the ticket — which is the whole
                  reason «מחיקה» is a different word. Absent at `intake`, which
                  cannot be undone. */}
              {mayWork && ticket.stage !== "intake" && (
                <Button
                  data-control="undo"
                  variant="ghost"
                  size="md"
                  fullWidthMobile={false}
                  loading={busyControl === "undo"}
                  aria-label={t("atelier.undoAria", { name })}
                  onClick={() => onUndo(ticket)}
                >
                  {t("atelier.undo")}
                </Button>
              )}
              {mayEdit && (
                <Button
                  data-control="edit"
                  variant="ghost"
                  size="md"
                  fullWidthMobile={false}
                  aria-label={t("atelier.editAria", { name })}
                  onClick={() => onEdit(ticket)}
                >
                  {t("atelier.edit")}
                </Button>
              )}
              {/* The ONLY `danger` on this screen, and the only irreversible act
                  on it — which is why it is the one that asks before it writes. */}
              {elevated && (
                <Button
                  data-control="delete"
                  variant="danger"
                  size="md"
                  fullWidthMobile={false}
                  aria-label={t("atelier.deleteAria", { name })}
                  onClick={() => onDelete(ticket)}
                >
                  {t("atelier.delete")}
                </Button>
              )}
            </div>
          </div>
        )}

        {alert !== null && (
          /* A board-level error names no ticket, so the alert lives INSIDE the
             card, under the controls, and takes focus. */
          <p
            ref={alertRef}
            data-control="alert"
            role="alert"
            tabIndex={-1}
            className="text-sm text-danger"
          >
            {alert}
          </p>
        )}
      </Card>
    </li>
  );
}
