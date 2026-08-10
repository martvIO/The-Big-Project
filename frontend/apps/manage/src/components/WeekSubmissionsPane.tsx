import { useCallback, useEffect, useState } from "react";
import { Trans, useTranslation } from "react-i18next";
import { Badge, Button, Card, Skeleton, formatDateRange } from "@boutique/ui";
import { api, ApiError, errorMessage } from "../api";
import type { AvailabilityState, ShiftTemplate, WeekSubmissionRow } from "../api";
import { RangeText } from "../lib/dateRange";
import { DAY_NAMES, addDays } from "../lib/week";
import { plainDayMonth } from "../lib/jerusalem";
import { ShiftAvailabilityFieldset, UNANSWERED } from "./ShiftAvailabilityFieldset";

// Roster readiness (elevated only): who has answered, and the on-behalf write.
//
// ⚠ THE UNSUBMITTED WEEK IS NOT AN EMPTY STATE. «הגישו 0 מתוך 8» over eight
// «טרם הגישה» rows is the correct and informative Monday render; an `EmptyState`
// would announce a fault where there is a schedule.

const MAPPED_CODES: Record<string, string> = {
  SUBMISSION_CLOSED: "shifts.errors.closed",
  WEEK_OUT_OF_RANGE: "shifts.errors.weekOutOfRange",
  NOT_AUTHORIZED: "shifts.errors.notAuthorized",
  NOT_FOUND: "shifts.errors.notFound",
};

const hhmm = (time: string) => time.slice(0, 5);

export interface WeekSubmissionsPaneProps {
  // Read by the container, which needs them anyway to decide the first-run
  // branch. The expanded row cannot render a legend or a weekday heading without
  // them, and a second read here could disagree with the one the container
  // already branched on.
  templates: ShiftTemplate[];
}

type Answers = Record<string, AvailabilityState | null>;

function answersOf(row: WeekSubmissionRow, templates: ShiftTemplate[]): Answers {
  const answers: Answers = {};
  for (const template of templates) {
    answers[template.id] = UNANSWERED;
  }
  for (const entry of row.entries) {
    answers[entry.shift_template_id] = entry.state;
  }
  return answers;
}

function byWeekday(templates: ShiftTemplate[]): [number, ShiftTemplate[]][] {
  const groups = new Map<number, ShiftTemplate[]>();
  for (const template of templates) {
    const day = groups.get(template.day_of_week) ?? [];
    day.push(template);
    groups.set(template.day_of_week, day);
  }
  return [...groups.entries()].sort(([a], [b]) => a - b);
}

export function WeekSubmissionsPane({ templates }: WeekSubmissionsPaneProps) {
  const { t } = useTranslation();
  const [weekStart, setWeekStart] = useState<string | null>(null);
  const [weekEnd, setWeekEnd] = useState<string | null>(null);
  const [rows, setRows] = useState<WeekSubmissionRow[] | null>(null);
  const [loadFailed, setLoadFailed] = useState(false);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [answers, setAnswers] = useState<Answers>({});
  const [saveError, setSaveError] = useState<string | null>(null);
  const [savedFor, setSavedFor] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setLoadFailed(false);
    try {
      const payload = await api.getWeekSubmissions();
      setRows(payload.rows);
      setWeekStart(payload.week_start);
      setWeekEnd(payload.week_end);
    } catch {
      setRows(null);
      setLoadFailed(true);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const expand = (row: WeekSubmissionRow) => {
    setSaveError(null);
    setSavedFor(null);
    if (expanded === row.staff_user_id) {
      setExpanded(null);
      return;
    }
    setExpanded(row.staff_user_id);
    setAnswers(answersOf(row, templates));
  };

  const saveFor = async (row: WeekSubmissionRow) => {
    if (weekStart === null) {
      return;
    }
    setSaving(true);
    setSaveError(null);
    try {
      // ⚠ ONE REQUEST, NEVER A WRITE PER TAP. D11's `PUT` is a whole-week
      // replace, so a per-tap write would resend her complete entry set twelve
      // times — twelve full-week replaces, twelve audit rows and a race with her
      // own save.
      const payload = await api.submitAvailability({
        week_start: weekStart,
        staff_user_id: row.staff_user_id,
        entries: Object.entries(answers)
          .filter(([, state]) => state !== UNANSWERED)
          .map(([shift_template_id, state]) => ({
            shift_template_id,
            state: state as AvailabilityState,
          })),
      });
      // PATCH, DON'T REFETCH (F51's rule): the row we just wrote is the one the
      // server answered with, so the badge flips from the write's own response
      // rather than from a second read that could race it.
      setRows((current) =>
        current === null
          ? current
          : current.map((existing) =>
              existing.staff_user_id === row.staff_user_id
                ? { ...existing, submitted: payload.entries.length > 0, entries: payload.entries }
                : existing,
            ),
      );
      setSavedFor(row.staff_user_id);
    } catch (error) {
      const code = error instanceof ApiError ? error.code : null;
      const key = code === null ? undefined : MAPPED_CODES[code];
      setSaveError(key === undefined ? errorMessage(error) : t(key));
    } finally {
      setSaving(false);
    }
  };

  if (rows === null) {
    return (
      <Card>
        <h2 className="text-xl font-semibold text-ink">{t("shifts.submissionsHeading")}</h2>
        {loadFailed ? (
          <div className="mt-4 flex flex-col items-start gap-2">
            <p role="alert" className="text-base text-danger">
              {t("shifts.loadFailed")}
            </p>
            <Button variant="secondary" size="md" onClick={() => void load()}>
              {t("shifts.retry")}
            </Button>
          </div>
        ) : (
          <Skeleton variant="text" lines={4} />
        )}
      </Card>
    );
  }

  // Not-yet rows FIRST: the owner opens this screen to find who is missing.
  const ordered = [...rows].sort((a, b) => Number(a.submitted) - Number(b.submitted));
  const submittedCount = rows.filter((row) => row.submitted).length;

  return (
    <Card>
      <h2 className="text-xl font-semibold text-ink">{t("shifts.submissionsHeading")}</h2>

      {weekStart !== null && weekEnd !== null && (
        <p role="status" className="mt-3 text-base text-ink">
          {t("shifts.weekLabel")} <RangeText range={formatDateRange(weekStart, weekEnd)} />
        </p>
      )}
      <p className="mt-1 text-base text-ink">
        {t("shifts.submittedCount", { submitted: submittedCount, total: rows.length })}
      </p>

      <ul className="mt-4 flex flex-col gap-3">
        {ordered.map((row) => (
          <li key={row.staff_user_id} className="flex flex-col gap-2 border-t border-border pt-3">
            <div className="flex flex-wrap items-center gap-2">
              {/* A BARE <bdi> — a `dir="ltr"` on a Hebrew name is itself a
                  defect (R19), and `break-words` keeps a long one inside the
                  720px column rather than pushing the badge out of it. */}
              <bdi className="break-words text-base text-ink">{row.display_name}</bdi>
              {/* The WORD carries the state; the variant is redundant
                  reinforcement that survives greyscale. */}
              <Badge variant={row.submitted ? "success" : "warning"}>
                {t(row.submitted ? "shifts.submitted" : "shifts.notSubmitted")}
              </Badge>
              {row.submitted && (
                <span className="text-sm text-ink-muted">
                  {t("shifts.answered", {
                    answered: row.entries.length,
                    total: templates.length,
                  })}
                </span>
              )}
              <Button
                variant="secondary"
                size="md"
                onClick={() => {
                  expand(row);
                }}
              >
                {expanded === row.staff_user_id ? (
                  t("shifts.close")
                ) : (
                  <Trans
                    i18nKey="shifts.expandRow"
                    values={{ name: row.display_name }}
                    components={{ bdi: <bdi /> }}
                  />
                )}
              </Button>
            </div>

            {expanded === row.staff_user_id && (
              <div className="flex flex-col gap-4">
                <p className="text-sm text-ink-muted">{t("shifts.onBehalfNote")}</p>
                {/* ⚠ THE WEEKDAY GROUPING IS NOT DECORATION. `label` is free
                    operator text with no uniqueness rule, and D3's day-carrying
                    auto-labels are replaced the moment she splits a day — so
                    without it a shift manager sees six legends all reading
                    «משמרת בוקר · 09:00–14:00» and records against the wrong day,
                    a write that stamps `recorded_by` permanently and surfaces on
                    the staffer's own screen. */}
                {byWeekday(templates).map(([day, dayTemplates]) => (
                  <section key={day} className="flex flex-col gap-3">
                    <h3 className="text-base font-semibold text-ink">
                      {t("shifts.dayHeading", {
                        day: DAY_NAMES[day],
                        date:
                          weekStart === null ? "" : plainDayMonth(addDays(weekStart, day)),
                      })}
                    </h3>
                    {dayTemplates.map((template) => (
                      <ShiftAvailabilityFieldset
                        key={template.id}
                        templateId={template.id}
                        legend={`${template.label} · ${hhmm(template.starts_at_time)}–${hhmm(template.ends_at_time)}`}
                        value={answers[template.id] ?? UNANSWERED}
                        onChange={(state) => {
                          setAnswers((current) => ({ ...current, [template.id]: state }));
                          setSavedFor(null);
                        }}
                      />
                    ))}
                  </section>
                ))}
                <div className="flex flex-wrap items-center gap-3">
                  <Button size="md" loading={saving} onClick={() => void saveFor(row)}>
                    <Trans
                      i18nKey="shifts.onBehalfSave"
                      values={{ name: row.display_name }}
                      components={{ bdi: <bdi /> }}
                    />
                  </Button>
                  {savedFor === row.staff_user_id && (
                    <span role="status" className="text-sm text-ink-muted">
                      <Trans
                        i18nKey="shifts.onBehalfDone"
                        values={{ name: row.display_name }}
                        components={{ bdi: <bdi /> }}
                      />
                    </span>
                  )}
                </div>
                {saveError !== null && (
                  <p role="alert" className="text-base text-danger">
                    {saveError}
                  </p>
                )}
              </div>
            )}
          </li>
        ))}
      </ul>
    </Card>
  );
}
