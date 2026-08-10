import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Button, Card, Skeleton, formatDateRange } from "@boutique/ui";
import { api, ApiError, errorMessage } from "../api";
import type { AvailabilityState, ShiftTemplate, ShiftWeek } from "../api";
import { RangeText } from "../lib/dateRange";
import { jerusalemIsoDate, jerusalemTime, jerusalemWeekday, plainDayMonth } from "../lib/jerusalem";
import { DAY_NAMES, addDays } from "../lib/week";
import { ShiftAvailabilityFieldset, UNANSWERED } from "./ShiftAvailabilityFieldset";

// The staffer's screen, and the highest-volume surface in this feature by an
// order of magnitude — eight staffers × 52 weeks against one owner configuring
// templates once. Everything here is arranged around her tap budget.
//
// ⚠ NO POLLING, NO TIMER, NO LIVE COUNTER. This is a FORM. A workroom phone
// should not run a second loop (`App.tsx`'s own argument), and with no timer
// anywhere SC 2.2.2 does not apply.
//
// ⚠ NO HOUR TOTALS ANYWHERE. This is not an hours-worked record and must never
// read as one — the epic's labour-law row makes that drift review-blocking. A
// shift shows `HH:MM–HH:MM` because that is how she recognises which shift she
// is answering; the moment a screen adds them up it is an attendance sheet.

// The four codes this panel speaks Hebrew for. Everything else falls through to
// `errorMessage(error)` and shows the server's own text — which is the visible
// failure mode F38's build note names, and is better than a silent wrong
// sentence.
//
// NOT pinned by anything: `SPEC_ERROR_CODES` in `test_shifts_api.py` is a Python
// set checked against Python. A sixth code would render in English on a green
// build, and the remedy is to add it here by hand.
const MAPPED_CODES: Record<string, string> = {
  SUBMISSION_CLOSED: "shifts.errors.closed",
  WEEK_OUT_OF_RANGE: "shifts.errors.weekOutOfRange",
  NOT_AUTHORIZED: "shifts.errors.notAuthorized",
  NOT_FOUND: "shifts.errors.notFound",
};

// D1's window, mirrored so the two week buttons disable at the edges rather
// than letting her walk into a 400. The server validates it regardless — this
// is a courtesy, never the rule.
//
// ⚠ THE OFFSET IS COUNTED FROM THE SERVER'S DEFAULT WEEK, NOT FROM A DEVICE
// CLOCK. The panel never computes «next week»: that changes meaning at Saturday
// midnight and a browser on a New York clock disagrees with the server for part
// of every day, which is `lib/jerusalem.ts`' whole reason for existing. The
// first load's week IS the server's default — NEXT week, i.e. +1 from the
// current one — so the window `[-4, +4]` around the current week is
// `[-5, +3]` around this origin.
const DAYS_IN_WEEK = 7;
const FIRST_OFFSET = -5;
const LAST_OFFSET = 3;

export interface MyWeekPanelProps {
  // The owner and the shift manager are not subject to the deadline (D5), which
  // the SERVER already expresses through `locked` — this flag only picks the
  // muted «you are past the deadline» line over the locked banner.
  elevated: boolean;
}

type Answers = Record<string, AvailabilityState | null>;

function answersOf(week: ShiftWeek): Answers {
  const answers: Answers = {};
  for (const template of week.templates) {
    answers[template.id] = UNANSWERED;
  }
  for (const entry of week.entries) {
    answers[entry.shift_template_id] = entry.state;
  }
  return answers;
}

function recordersOf(week: ShiftWeek): Record<string, string | null> {
  return Object.fromEntries(
    week.entries.map((entry) => [entry.shift_template_id, entry.recorded_by_name]),
  );
}

// Groups by weekday, preserving the server's `(day, sort_order, starts_at_time)`
// order within each. Weekdays with no template are absent entirely — a Saturday
// heading over nothing is chrome that says "you are missing something".
function byWeekday(templates: ShiftTemplate[]): [number, ShiftTemplate[]][] {
  const groups = new Map<number, ShiftTemplate[]>();
  for (const template of templates) {
    const day = groups.get(template.day_of_week) ?? [];
    day.push(template);
    groups.set(template.day_of_week, day);
  }
  return [...groups.entries()].sort(([a], [b]) => a - b);
}

// "09:00:00" -> "09:00". The backend serialises TIME as HH:MM:SS;
// `HoursSection`'s shipped `toInputTime` rule.
const hhmm = (time: string) => time.slice(0, 5);

export function MyWeekPanel({ elevated }: MyWeekPanelProps) {
  const { t } = useTranslation();
  const [weekStart, setWeekStart] = useState<string | undefined>(undefined);
  const [offset, setOffset] = useState(0);
  const [week, setWeek] = useState<ShiftWeek | null>(null);
  const [answers, setAnswers] = useState<Answers>({});
  const [loadFailed, setLoadFailed] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [saving, setSaving] = useState(false);
  // ⚠ SET WHEN A SAVE IS REFUSED WITH `SUBMISSION_CLOSED`, so the focus effect
  // fires on the render that carries the answer rather than on every lock.
  const [justClosed, setJustClosed] = useState(false);
  const lockedBanner = useRef<HTMLParagraphElement>(null);

  const load = useCallback(async () => {
    setLoadFailed(false);
    try {
      const payload = await api.getShiftWeek(weekStart);
      setWeek(payload);
      setAnswers(answersOf(payload));
      // ⚠ `weekStart` IS THE REQUESTED WEEK AND IS DELIBERATELY NOT OVERWRITTEN
      // WITH THE RESOLVED ONE. Writing the server's answer back into the
      // request state changes `load`'s identity, refires the effect, and costs
      // a SECOND fetch on every mount — for a value navigation already reads
      // off `week.week_start`.
    } catch {
      setWeek(null);
      setLoadFailed(true);
    }
  }, [weekStart]);

  useEffect(() => {
    void load();
  }, [load]);

  // ⚠ THE SAVE BUTTON SHE JUST PRESSED IS GONE on a `SUBMISSION_CLOSED` refusal
  // (the locked render removes it, §2.5-K), so focus falls to <body> and her
  // next Tab restarts at the skip link — after twelve answered shifts, that is a
  // traverse of the shell and the whole nav (WCAG 2.4.3). `BookingDetail`'s
  // shipped rescue: a `-1` destination focused in an effect keyed on the state
  // that carries the answer. A `.focus()` on the trigger is a no-op once the
  // trigger is gone.
  useEffect(() => {
    if (justClosed && lockedBanner.current !== null) {
      lockedBanner.current.focus();
      setJustClosed(false);
    }
  }, [justClosed]);

  const step = (weeks: number) => {
    if (week === null) {
      return;
    }
    setSaved(false);
    setSaveError(null);
    setOffset((current) => current + weeks);
    // ⚠ WALKS FROM THE REQUESTED WEEK, falling back to the resolved one only
    // on the first step. `week` is the LAST PAYLOAD, so a second press while a
    // load is still in flight would walk from a week she has already left.
    setWeekStart((current) => addDays(current ?? week.week_start, weeks * DAYS_IN_WEEK));
  };

  const markRestAvailable = () => {
    setAnswers((current) => {
      const next: Answers = { ...current };
      for (const [templateId, state] of Object.entries(current)) {
        // ⚠ ONLY the unanswered ones. Never overwriting an answer she already
        // gave is what makes this non-destructive BY CONSTRUCTION and removes
        // any need for an undo.
        if (state === UNANSWERED) {
          next[templateId] = "available";
        }
      }
      return next;
    });
    setSaved(false);
  };

  const save = async () => {
    if (week === null) {
      return;
    }
    setSaving(true);
    setSaveError(null);
    try {
      const payload = await api.submitAvailability({
        week_start: week.week_start,
        // A template sitting on «לא נרשם» is OMITTED, which is D8's clear path
        // and D11's soft-delete-on-absence.
        entries: Object.entries(answers)
          .filter(([, state]) => state !== UNANSWERED)
          .map(([shift_template_id, state]) => ({
            shift_template_id,
            state: state as AvailabilityState,
          })),
      });
      setWeek(payload);
      setAnswers(answersOf(payload));
      setSaved(true);
    } catch (error) {
      const code = error instanceof ApiError ? error.code : null;
      const key = code === null ? undefined : MAPPED_CODES[code];
      setSaveError(key === undefined ? errorMessage(error) : t(key));
      if (code === "SUBMISSION_CLOSED" || code === "WEEK_OUT_OF_RANGE" || code === "NOT_FOUND") {
        // The screen and the flow must not disagree: refetch so the panel shows
        // what is really true now. `SUBMISSION_CLOSED` additionally moves focus.
        setJustClosed(code === "SUBMISSION_CLOSED");
        await load();
      }
    } finally {
      setSaving(false);
    }
  };

  const answered = Object.values(answers).filter((state) => state !== UNANSWERED).length;

  return (
    <Card>
      <h2 className="text-xl font-semibold text-ink">{t("shifts.myWeekHeading")}</h2>

      {week === null && !loadFailed && <Skeleton variant="text" lines={4} />}

      {loadFailed && (
        <div className="mt-4 flex flex-col items-start gap-2">
          <p role="alert" className="text-base text-danger">
            {t("shifts.loadFailed")}
          </p>
          <Button variant="secondary" size="md" onClick={() => void load()}>
            {t("shifts.retry")}
          </Button>
        </div>
      )}

      {week !== null && (
        <div className="mt-4 flex flex-col gap-6">
          <div className="flex flex-wrap items-center gap-2">
            {/* WORDS, NOT CHEVRONS (DL20): this console ships no icon-only
                control, and there is no directional glyph to get backwards in
                RTL. Disabled at D1's ±4 edges. */}
            <Button
              variant="secondary"
              size="md"
              disabled={offset <= FIRST_OFFSET}
              onClick={() => {
                step(-1);
              }}
            >
              {t("shifts.prevWeek")}
            </Button>
            <Button
              variant="secondary"
              size="md"
              disabled={offset >= LAST_OFFSET}
              onClick={() => {
                step(1);
              }}
            >
              {t("shifts.nextWeek")}
            </Button>
            {/* role="status": a week change alters the whole pane under a button
                that never moved, so it has no other voice. */}
            <p role="status" className="text-base text-ink">
              {t("shifts.weekLabel")}{" "}
              <RangeText range={formatDateRange(week.week_start, week.week_end)} />
            </p>
          </div>

          <p className="text-sm text-ink-muted">
            {/* ⚠ `jerusalemIsoDate` FIRST. `plainDayMonth` splits a plain
                YYYY-MM-DD on `-`, so the raw instant renders «NaN.11»; and
                slicing the instant by hand reads a UTC calendar day as
                Jerusalem's, which for a «01:00» deadline names the wrong day
                every time. */}
            {t("shifts.deadline", {
              day: `${jerusalemWeekday(week.deadline_at)}, ${plainDayMonth(jerusalemIsoDate(week.deadline_at))}`,
              time: jerusalemTime(week.deadline_at),
            })}
          </p>

          {week.templates.length === 0 && (
            <div className="py-8 text-center">
              <p className="text-base text-ink">{t("shifts.noTemplates")}</p>
              {/* NO ACTION: the seed lives in ShiftTemplatesPane and has exactly
                  one owner. Offering it here would be a door that 403s. */}
              <p className="mx-auto mt-2 max-w-[40ch] text-base text-ink-muted">
                {t("shifts.noTemplatesStaffBody")}
              </p>
            </div>
          )}

          {week.locked && !elevated && (
            <p
              role="status"
              ref={lockedBanner}
              tabIndex={-1}
              className="rounded-md bg-surface-raised p-3 text-base text-ink"
            >
              {t("shifts.locked")}
            </p>
          )}
          {week.locked && elevated && (
            <p className="text-sm text-ink-muted">{t("shifts.lockedElevated")}</p>
          )}

          {week.templates.length > 0 && !week.locked && (
            <Button variant="secondary" size="md" onClick={markRestAvailable}>
              {t("shifts.markRestAvailable")}
            </Button>
          )}

          {week.locked ? (
            // ⚠ A `<dl>` OF HER ANSWERS, NOT DISABLED RADIOS. A disabled control
            // is not focusable, so a keyboard or screen-reader user in a locked
            // week could not reach the answers she already gave — the one thing
            // the locked screen exists to show her. Less DOM, fully readable,
            // and zero disabled controls for axe to reason about.
            <dl className="flex flex-col gap-2">
              {week.templates.map((template) => (
                <div key={template.id} className="flex flex-wrap items-baseline gap-2">
                  <dt className="text-base text-ink">
                    {DAY_NAMES[template.day_of_week]} · {template.label} ·{" "}
                    <bdi dir="ltr">
                      {hhmm(template.starts_at_time)}–{hhmm(template.ends_at_time)}
                    </bdi>
                  </dt>
                  <dd className="text-base font-semibold text-ink">
                    {t(stateKey(answers[template.id]))}
                  </dd>
                </div>
              ))}
            </dl>
          ) : (
            byWeekday(week.templates).map(([day, templates]) => (
              <section key={day} className="flex flex-col gap-4">
                <h3 className="text-base font-semibold text-ink">
                  {t("shifts.dayHeading", {
                    day: DAY_NAMES[day],
                    // ⚠ `addDays` ON THE PLAIN WIRE DATE. `new Date(week_start).getDate() + n`
                    // renders the 7th for a week that starts on the 8th under
                    // this suite's TZ=America/New_York.
                    date: plainDayMonth(addDays(week.week_start, day)),
                  })}
                </h3>
                {templates.map((template) => (
                  <ShiftAvailabilityFieldset
                    key={template.id}
                    templateId={template.id}
                    legend={`${template.label} · ${hhmm(template.starts_at_time)}–${hhmm(template.ends_at_time)}`}
                    value={answers[template.id] ?? UNANSWERED}
                    recordedByName={recordersOf(week)[template.id] ?? null}
                    onChange={(state) => {
                      setAnswers((current) => ({ ...current, [template.id]: state }));
                      setSaved(false);
                    }}
                  />
                ))}
              </section>
            ))
          )}

          {week.templates.length > 0 && (
            // The SECOND live region on this pane, and it is what makes
            // «סימון כל השאר כזמינה» usable without sight: that button silently
            // mutates up to twelve groups and its own name does not change, so
            // the progress line is the only evidence anything happened. No new
            // copy key — a second sentence about a number the first one already
            // carries could drift from it.
            <p role="status" className="text-sm text-ink-muted">
              {t("shifts.answered", { answered, total: week.templates.length })}
            </p>
          )}

          {/* ⚠ REMOVED WHEN LOCKED, NOT DISABLED. A disabled save on a locked
              form is a control that promises an act it cannot perform. */}
          {!week.locked && week.templates.length > 0 && (
            <div className="flex flex-wrap items-center gap-3">
              <Button size="md" onClick={() => void save()} loading={saving}>
                {t("shifts.save")}
              </Button>
              {saved && (
                <span role="status" className="text-sm text-ink-muted">
                  {t("common.saved")}
                </span>
              )}
            </div>
          )}

          {saveError !== null && (
            <p role="alert" className="text-base text-danger">
              {saveError}
            </p>
          )}
        </div>
      )}
    </Card>
  );
}

function stateKey(state: AvailabilityState | null | undefined): string {
  switch (state) {
    case "available":
      return "shifts.states.available";
    case "unavailable":
      return "shifts.states.unavailable";
    case "preferred":
      return "shifts.states.preferred";
    default:
      return "shifts.stateUnanswered";
  }
}
