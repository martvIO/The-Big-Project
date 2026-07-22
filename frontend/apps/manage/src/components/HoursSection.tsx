import { useCallback, useEffect, useState } from "react";
import type { FormEvent } from "react";
import { api, errorMessage } from "../api";
import type { AvailabilityException, WeeklyRuleInput } from "../api";
import { validateExceptionTimes, validateWeeklyRules } from "../validation";
import {
  cardClass,
  dangerButtonClass,
  ErrorNotice,
  inputClass,
  labelClass,
  Loading,
  primaryButtonClass,
  SavedNotice,
  secondaryButtonClass,
} from "./shared";

// 0=Sunday … 6=Saturday (Israeli week).
const DAY_NAMES = ["ראשון", "שני", "שלישי", "רביעי", "חמישי", "שישי", "שבת"];

// Backend serializes TIME as HH:MM:SS; <input type="time"> wants HH:MM.
const toInputTime = (time: string) => time.slice(0, 5);

function formatDate(isoDate: string): string {
  return new Intl.DateTimeFormat("he-IL", { dateStyle: "medium" }).format(
    new Date(`${isoDate}T00:00:00`),
  );
}

export function HoursSection() {
  const [rules, setRules] = useState<WeeklyRuleInput[] | null>(null);
  const [exceptions, setExceptions] = useState<AvailabilityException[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [rulesError, setRulesError] = useState<string | null>(null);
  const [rulesSaved, setRulesSaved] = useState(false);
  const [savingRules, setSavingRules] = useState(false);

  const [exceptionDate, setExceptionDate] = useState("");
  const [closedAllDay, setClosedAllDay] = useState(true);
  const [exceptionOpen, setExceptionOpen] = useState("");
  const [exceptionClose, setExceptionClose] = useState("");
  const [exceptionNote, setExceptionNote] = useState("");
  const [exceptionError, setExceptionError] = useState<string | null>(null);
  const [addingException, setAddingException] = useState(false);

  const load = useCallback(async () => {
    try {
      const availability = await api.getAvailability();
      setRules(
        availability.rules.map((rule) => ({
          day_of_week: rule.day_of_week,
          open_time: toInputTime(rule.open_time),
          close_time: toInputTime(rule.close_time),
          capacity: rule.capacity,
        })),
      );
      setExceptions(availability.exceptions);
      setLoadError(null);
    } catch (error) {
      setLoadError(errorMessage(error));
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  if (loadError !== null && rules === null) {
    return <ErrorNotice message={loadError} />;
  }
  if (rules === null) {
    return <Loading />;
  }

  const updateRule = (index: number, patch: Partial<WeeklyRuleInput>) => {
    setRules(rules.map((rule, at) => (at === index ? { ...rule, ...patch } : rule)));
    setRulesSaved(false);
  };

  const handleSaveRules = async () => {
    const invalid = validateWeeklyRules(rules);
    if (invalid !== null) {
      setRulesError(invalid);
      return;
    }
    setSavingRules(true);
    setRulesSaved(false);
    try {
      const saved = await api.replaceWeeklyRules(rules);
      setRules(
        saved.map((rule) => ({
          day_of_week: rule.day_of_week,
          open_time: toInputTime(rule.open_time),
          close_time: toInputTime(rule.close_time),
          capacity: rule.capacity,
        })),
      );
      setRulesError(null);
      setRulesSaved(true);
    } catch (error) {
      setRulesError(errorMessage(error));
    } finally {
      setSavingRules(false);
    }
  };

  const handleAddException = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!exceptionDate) {
      setExceptionError("יש לבחור תאריך");
      return;
    }
    const openTime = closedAllDay ? null : exceptionOpen || null;
    const closeTime = closedAllDay ? null : exceptionClose || null;
    if (!closedAllDay && (openTime === null || closeTime === null)) {
      setExceptionError("יש להזין שעות פתיחה וסגירה, או לסמן סגור כל היום");
      return;
    }
    const invalid = validateExceptionTimes(openTime, closeTime);
    if (invalid !== null) {
      setExceptionError(invalid);
      return;
    }
    setAddingException(true);
    try {
      const created = await api.addAvailabilityException({
        date: exceptionDate,
        open_time: openTime,
        close_time: closeTime,
        note: exceptionNote.trim() === "" ? null : exceptionNote.trim(),
      });
      setExceptions([created, ...exceptions]);
      setExceptionDate("");
      setClosedAllDay(true);
      setExceptionOpen("");
      setExceptionClose("");
      setExceptionNote("");
      setExceptionError(null);
    } catch (error) {
      setExceptionError(errorMessage(error));
    } finally {
      setAddingException(false);
    }
  };

  const handleRemoveException = async (id: string) => {
    try {
      await api.removeAvailabilityException(id);
      setExceptions(exceptions.filter((exception) => exception.id !== id));
      setExceptionError(null);
    } catch (error) {
      setExceptionError(errorMessage(error));
    }
  };

  return (
    <div className="space-y-6">
      <section className={`${cardClass} space-y-4`}>
        <h3 className="text-sm font-semibold">שעות פעילות שבועיות</h3>
        {rules.length === 0 && (
          <p className="text-sm text-stone-500">אין עדיין חלונות פעילות — הוסיפי חלון ראשון.</p>
        )}
        <ul className="space-y-2">
          {rules.map((rule, index) => (
            // Index keys are fine here: rows are edited in place and only
            // appended/removed at known positions.
            <li key={index} className="flex flex-wrap items-end gap-3">
              <div>
                <label className={labelClass} htmlFor={`rule-day-${index}`}>
                  יום
                </label>
                <select
                  id={`rule-day-${index}`}
                  className={inputClass}
                  value={rule.day_of_week}
                  onChange={(event) => updateRule(index, { day_of_week: Number(event.target.value) })}
                >
                  {DAY_NAMES.map((name, day) => (
                    <option key={day} value={day}>
                      {name}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className={labelClass} htmlFor={`rule-open-${index}`}>
                  פתיחה
                </label>
                <input
                  id={`rule-open-${index}`}
                  type="time"
                  className={inputClass}
                  value={rule.open_time}
                  onChange={(event) => updateRule(index, { open_time: event.target.value })}
                />
              </div>
              <div>
                <label className={labelClass} htmlFor={`rule-close-${index}`}>
                  סגירה
                </label>
                <input
                  id={`rule-close-${index}`}
                  type="time"
                  className={inputClass}
                  value={rule.close_time}
                  onChange={(event) => updateRule(index, { close_time: event.target.value })}
                />
              </div>
              <div>
                <label className={labelClass} htmlFor={`rule-capacity-${index}`}>
                  קיבולת
                </label>
                <input
                  id={`rule-capacity-${index}`}
                  type="number"
                  min={1}
                  className={inputClass}
                  value={rule.capacity}
                  onChange={(event) => updateRule(index, { capacity: Number(event.target.value) })}
                />
              </div>
              <button
                type="button"
                className={dangerButtonClass}
                onClick={() => {
                  setRules(rules.filter((_, at) => at !== index));
                  setRulesSaved(false);
                }}
              >
                הסרה
              </button>
            </li>
          ))}
        </ul>
        <div className="flex gap-3">
          <button
            type="button"
            className={secondaryButtonClass}
            onClick={() => {
              setRules([
                ...rules,
                { day_of_week: 0, open_time: "09:00", close_time: "17:00", capacity: 1 },
              ]);
              setRulesSaved(false);
            }}
          >
            הוספת חלון
          </button>
          <button
            type="button"
            className={primaryButtonClass}
            disabled={savingRules}
            onClick={() => void handleSaveRules()}
          >
            שמירת שעות פעילות
          </button>
        </div>
        {rulesError !== null && <ErrorNotice message={rulesError} />}
        {rulesSaved && <SavedNotice />}
      </section>

      <section className={`${cardClass} space-y-4`}>
        <h3 className="text-sm font-semibold">תאריכים חריגים</h3>
        <form onSubmit={(event) => void handleAddException(event)} className="space-y-3">
          <div className="flex flex-wrap items-end gap-3">
            <div>
              <label className={labelClass} htmlFor="exception-date">
                תאריך
              </label>
              <input
                id="exception-date"
                type="date"
                className={inputClass}
                value={exceptionDate}
                onChange={(event) => setExceptionDate(event.target.value)}
              />
            </div>
            <label className="flex items-center gap-2 pb-2 text-sm">
              <input
                type="checkbox"
                checked={closedAllDay}
                onChange={(event) => setClosedAllDay(event.target.checked)}
              />
              סגור כל היום
            </label>
            {!closedAllDay && (
              <>
                <div>
                  <label className={labelClass} htmlFor="exception-open">
                    פתיחה
                  </label>
                  <input
                    id="exception-open"
                    type="time"
                    className={inputClass}
                    value={exceptionOpen}
                    onChange={(event) => setExceptionOpen(event.target.value)}
                  />
                </div>
                <div>
                  <label className={labelClass} htmlFor="exception-close">
                    סגירה
                  </label>
                  <input
                    id="exception-close"
                    type="time"
                    className={inputClass}
                    value={exceptionClose}
                    onChange={(event) => setExceptionClose(event.target.value)}
                  />
                </div>
              </>
            )}
            <div className="grow">
              <label className={labelClass} htmlFor="exception-note">
                הערה
              </label>
              <input
                id="exception-note"
                className={inputClass}
                value={exceptionNote}
                onChange={(event) => setExceptionNote(event.target.value)}
              />
            </div>
            <button type="submit" className={primaryButtonClass} disabled={addingException}>
              הוספת חריגה
            </button>
          </div>
        </form>
        {exceptionError !== null && <ErrorNotice message={exceptionError} />}
        {exceptions.length === 0 ? (
          <p className="text-sm text-stone-500">אין תאריכים חריגים.</p>
        ) : (
          <ul className="space-y-2">
            {exceptions.map((exception) => (
              <li
                key={exception.id}
                className="flex flex-wrap items-center gap-3 border-b border-stone-100 pb-2 text-sm last:border-b-0"
              >
                <span className="font-medium">{formatDate(exception.date)}</span>
                {exception.open_time === null || exception.close_time === null ? (
                  <span className="rounded bg-red-100 px-2 py-0.5 text-xs text-red-800">
                    סגור כל היום
                  </span>
                ) : (
                  <span className="rounded bg-stone-100 px-2 py-0.5 text-xs text-stone-700">
                    שעות מיוחדות {toInputTime(exception.open_time)}–
                    {toInputTime(exception.close_time)}
                  </span>
                )}
                {exception.note !== null && (
                  <span className="text-stone-500">{exception.note}</span>
                )}
                <button
                  type="button"
                  className={`${dangerButtonClass} mr-auto`}
                  onClick={() => void handleRemoveException(exception.id)}
                >
                  הסרה
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
