import { useCallback, useEffect, useState } from "react";
import type { FormEvent } from "react";
import { Badge, Button, Card, Input, Modal, Select, Skeleton, Toggle } from "@boutique/ui";
import { api, errorMessage } from "../api";
import type { AvailabilityException, WeeklyRuleInput } from "../api";
import { validateExceptionTimes, validateWeeklyRules } from "../validation";

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
  const [pendingRemoval, setPendingRemoval] = useState<string | null>(null);

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
    return (
      <p role="alert" className="text-sm text-ink-muted">
        {loadError}
      </p>
    );
  }
  if (rules === null) {
    return <Skeleton variant="text" lines={4} />;
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

  const confirmRemoveException = () => {
    const id = pendingRemoval;
    setPendingRemoval(null);
    if (id !== null) {
      void handleRemoveException(id);
    }
  };

  return (
    <div className="space-y-6">
      <Card className="space-y-4">
        <h3 className="text-sm font-semibold">שעות פעילות שבועיות</h3>
        {rules.length === 0 && (
          <p className="text-sm text-ink-muted">אין עדיין חלונות פעילות — הוסיפי חלון ראשון.</p>
        )}
        <ul className="space-y-2">
          {rules.map((rule, index) => (
            // Index keys are fine here: rows are edited in place and only
            // appended/removed at known positions.
            <li key={index} className="flex flex-wrap items-end gap-3">
              <Select
                label="יום"
                value={rule.day_of_week}
                onChange={(event) => updateRule(index, { day_of_week: Number(event.target.value) })}
              >
                {DAY_NAMES.map((name, day) => (
                  <option key={day} value={day}>
                    {name}
                  </option>
                ))}
              </Select>
              <Input
                label="פתיחה"
                type="time"
                value={rule.open_time}
                onChange={(event) => updateRule(index, { open_time: event.target.value })}
              />
              <Input
                label="סגירה"
                type="time"
                value={rule.close_time}
                onChange={(event) => updateRule(index, { close_time: event.target.value })}
              />
              <Input
                label="קיבולת"
                type="number"
                min={1}
                value={rule.capacity}
                onChange={(event) => updateRule(index, { capacity: Number(event.target.value) })}
              />
              <Button
                type="button"
                variant="danger"
                onClick={() => {
                  setRules(rules.filter((_, at) => at !== index));
                  setRulesSaved(false);
                }}
              >
                הסרה
              </Button>
            </li>
          ))}
        </ul>
        <div className="flex items-center gap-3">
          <Button
            type="button"
            variant="secondary"
            onClick={() => {
              setRules([
                ...rules,
                { day_of_week: 0, open_time: "09:00", close_time: "17:00", capacity: 1 },
              ]);
              setRulesSaved(false);
            }}
          >
            הוספת חלון
          </Button>
          <Button type="button" loading={savingRules} onClick={() => void handleSaveRules()}>
            שמירת שעות פעילות
          </Button>
          {rulesSaved && <span className="text-xs text-ink-muted">נשמר לפני רגע</span>}
        </div>
        {rulesError !== null && (
          <p role="alert" className="text-sm text-danger">
            {rulesError}
          </p>
        )}
      </Card>

      <Card className="space-y-4">
        <h3 className="text-sm font-semibold">תאריכים חריגים</h3>
        <form onSubmit={(event) => void handleAddException(event)} className="space-y-3">
          <div className="flex flex-wrap items-end gap-3">
            <Input
              label="תאריך"
              type="date"
              value={exceptionDate}
              onChange={(event) => setExceptionDate(event.target.value)}
            />
            <Toggle label="סגור כל היום" checked={closedAllDay} onCheckedChange={setClosedAllDay} />
            {!closedAllDay && (
              <>
                <Input
                  label="פתיחה"
                  type="time"
                  value={exceptionOpen}
                  onChange={(event) => setExceptionOpen(event.target.value)}
                />
                <Input
                  label="סגירה"
                  type="time"
                  value={exceptionClose}
                  onChange={(event) => setExceptionClose(event.target.value)}
                />
              </>
            )}
            <div className="grow">
              <Input
                label="הערה"
                value={exceptionNote}
                onChange={(event) => setExceptionNote(event.target.value)}
              />
            </div>
            <Button type="submit" loading={addingException}>
              הוספת חריגה
            </Button>
          </div>
        </form>
        {exceptionError !== null && (
          <p role="alert" className="text-sm text-danger">
            {exceptionError}
          </p>
        )}
        {exceptions.length === 0 ? (
          <p className="text-sm text-ink-muted">אין תאריכים חריגים.</p>
        ) : (
          <ul className="space-y-2">
            {exceptions.map((exception) => (
              <li
                key={exception.id}
                className="flex flex-wrap items-center gap-3 border-b border-border pb-2 text-sm last:border-b-0"
              >
                <span className="font-semibold">{formatDate(exception.date)}</span>
                {exception.open_time === null || exception.close_time === null ? (
                  <Badge variant="danger">סגור כל היום</Badge>
                ) : (
                  <Badge variant="muted">
                    שעות מיוחדות {toInputTime(exception.open_time)}–
                    {toInputTime(exception.close_time)}
                  </Badge>
                )}
                {exception.note !== null && (
                  <span className="text-ink-muted">{exception.note}</span>
                )}
                <Button
                  type="button"
                  variant="danger"
                  className="ms-auto"
                  onClick={() => setPendingRemoval(exception.id)}
                >
                  הסרה
                </Button>
              </li>
            ))}
          </ul>
        )}
      </Card>

      <Modal
        open={pendingRemoval !== null}
        onClose={() => setPendingRemoval(null)}
        title="הסרת תאריך חריג"
        footer={
          <>
            <Button variant="ghost" onClick={() => setPendingRemoval(null)}>
              ביטול
            </Button>
            <Button variant="danger" onClick={confirmRemoveException}>
              הסרה
            </Button>
          </>
        }
      >
        האם להסיר את התאריך החריג?
      </Modal>
    </div>
  );
}
