import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Button, Card, Select, Skeleton, TimeField } from "@boutique/ui";
import { api, errorMessage } from "../api";
import type { SchedulingSettings } from "../api";
import { DAY_NAMES } from "../lib/week";

// The submission deadline (D6), in its OWN Card — not a `Modal` and not a block
// inside «משמרות הבוטיק». A dialog for two fields is chrome, and filing a
// submission deadline under a heading that says «the boutique's shifts» is a
// small lie about what the setting governs.
//
// ⚠ ONE SAVE FOR BOTH FIELDS, AND THAT IS STRUCTURAL. `merge_settings` is one
// atomic `settings = settings || :patch::jsonb` and `||` merges at the TOP LEVEL
// ONLY, so a patch carrying a partial `scheduling` object replaces the whole key
// and DELETES what it did not name. A "save day" button and a "save time" button
// would erase each other.
//
// It owns its OWN `api.getSettings()` read — `App.tsx` holds no settings state,
// and `ProfileSection` and `GatewaySection` each own theirs the same way. The
// values arrive DEFAULT-COMPLETE (D6), so nothing here needs `?? default`.
export function ShiftsDeadlineCard() {
  const { t } = useTranslation();
  const [draft, setDraft] = useState<SchedulingSettings | null>(null);
  const [loadFailed, setLoadFailed] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setLoadFailed(false);
    try {
      setDraft((await api.getSettings()).scheduling);
    } catch {
      setDraft(null);
      setLoadFailed(true);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const save = async () => {
    if (draft === null) {
      return;
    }
    setSaving(true);
    setSaveError(null);
    try {
      // BOTH fields, always. See the header.
      const settings = await api.updateSettings({ scheduling: draft });
      setDraft(settings.scheduling);
      setSaved(true);
    } catch (error) {
      setSaveError(errorMessage(error));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Card>
      <h2 className="text-xl font-semibold text-ink">{t("shifts.deadlineHeading")}</h2>

      {draft === null && !loadFailed && <Skeleton variant="text" lines={2} />}

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

      {draft !== null && (
        <div className="mt-4 flex flex-col gap-4">
          {/* The second sentence is D5 stated to the person who SETS the number:
              an owner choosing Wednesday 18:00 needs to know it does not lock
              her. */}
          <p className="max-w-prose text-base text-ink-muted">{t("shifts.deadlineHelp")}</p>
          <Select
            label={t("shifts.deadlineDay")}
            value={String(draft.submission_deadline_day_of_week)}
            onChange={(event) => {
              setDraft({ ...draft, submission_deadline_day_of_week: Number(event.target.value) });
              setSaved(false);
            }}
          >
            {DAY_NAMES.map((name, index) => (
              <option key={name} value={index}>
                {name}
              </option>
            ))}
          </Select>
          {/* The shared native `<input type="time">`: OS picker, OS locale,
              keyboard-complete, zero bytes. */}
          <TimeField
            label={t("shifts.deadlineTime")}
            value={draft.submission_deadline_time}
            onChange={(event) => {
              setDraft({ ...draft, submission_deadline_time: event.target.value });
              setSaved(false);
            }}
          />
          <div className="flex flex-wrap items-center gap-3">
            <Button size="md" loading={saving} onClick={() => void save()}>
              {t("shifts.deadlineSave")}
            </Button>
            {saved && (
              <span role="status" className="text-sm text-ink-muted">
                {t("common.saved")}
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
    </Card>
  );
}
