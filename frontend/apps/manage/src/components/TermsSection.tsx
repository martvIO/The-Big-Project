import { useCallback, useEffect, useState } from "react";
import type { FormEvent } from "react";
import { api, errorMessage } from "../api";
import type { TermsHistory } from "../api";
import { validateTerms } from "../validation";
import {
  cardClass,
  ErrorNotice,
  inputClass,
  labelClass,
  Loading,
  primaryButtonClass,
} from "./shared";

function formatDate(utcString: string): string {
  return new Intl.DateTimeFormat("he-IL", { dateStyle: "medium", timeStyle: "short" }).format(
    new Date(utcString),
  );
}

export function TermsSection() {
  const [history, setHistory] = useState<TermsHistory | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [termsText, setTermsText] = useState("");
  const [refundHours, setRefundHours] = useState("48");
  const [forfeitPercent, setForfeitPercent] = useState("100");
  const [formError, setFormError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    try {
      setHistory(await api.getTerms());
      setLoadError(null);
    } catch (error) {
      setHistory(null);
      setLoadError(errorMessage(error));
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const draft = {
      terms_text: termsText,
      refundable_until_hours_before: Number(refundHours),
      forfeit_percent: Number(forfeitPercent),
    };
    const invalid = validateTerms(draft);
    if (invalid !== null) {
      setFormError(invalid);
      return;
    }
    setSaving(true);
    try {
      await api.createTermsVersion(draft);
      setFormError(null);
      await load();
    } catch (error) {
      setFormError(errorMessage(error));
    } finally {
      setSaving(false);
    }
  };

  if (loadError !== null) {
    return <ErrorNotice message={loadError} />;
  }
  if (history === null) {
    return <Loading />;
  }

  const hasPolicy = history.versions.length > 0;

  return (
    <div className="space-y-6">
      {!hasPolicy && (
        <div
          data-testid="terms-setup-blocker"
          className="rounded-lg border-2 border-amber-400 bg-amber-50 p-4"
        >
          <h3 className="text-base font-semibold text-amber-900">
            עדיין לא הוגדרה מדיניות ביטולים
          </h3>
          <p className="mt-1 text-sm text-amber-800">
            לא ניתן לקבל הזמנות ללא מדיניות ביטולים פעילה — כל הזמנה מחייבת אישור תקנון. יש
            ליצור גרסה ראשונה למטה כדי להשלים את הקמת הבוטיק.
          </p>
        </div>
      )}

      {history.current !== null && (
        <div className={cardClass}>
          <h3 className="text-sm font-semibold">
            גרסה נוכחית: {history.current.version}
          </h3>
          <p className="mt-1 text-sm text-stone-600">
            החזר מלא עד {history.current.refundable_until_hours_before} שעות לפני התור · חילוט{" "}
            {history.current.forfeit_percent}% מהמקדמה מחוץ לחלון
          </p>
        </div>
      )}

      <form onSubmit={(event) => void handleSubmit(event)} className={`${cardClass} space-y-4`}>
        <h3 className="text-sm font-semibold">יצירת גרסה חדשה</h3>
        <p className="text-xs text-stone-500">
          כל שמירה יוצרת גרסה חדשה וקבועה — גרסאות קודמות נשמרות לעד ואינן ניתנות לעריכה.
        </p>
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label className={labelClass} htmlFor="terms-refund-hours">
              החזר מלא עד (שעות לפני התור)
            </label>
            <input
              id="terms-refund-hours"
              type="number"
              min={0}
              className={inputClass}
              value={refundHours}
              onChange={(event) => setRefundHours(event.target.value)}
            />
          </div>
          <div>
            <label className={labelClass} htmlFor="terms-forfeit-percent">
              אחוז חילוט מחוץ לחלון
            </label>
            <input
              id="terms-forfeit-percent"
              type="number"
              min={0}
              max={100}
              className={inputClass}
              value={forfeitPercent}
              onChange={(event) => setForfeitPercent(event.target.value)}
            />
          </div>
        </div>
        <div>
          <label className={labelClass} htmlFor="terms-text">
            תוכן מדיניות הביטולים
          </label>
          <textarea
            id="terms-text"
            rows={6}
            className={inputClass}
            value={termsText}
            onChange={(event) => setTermsText(event.target.value)}
          />
        </div>
        {formError !== null && <ErrorNotice message={formError} />}
        <button type="submit" className={primaryButtonClass} disabled={saving}>
          שמירת גרסה חדשה
        </button>
      </form>

      {hasPolicy && (
        <div className={cardClass}>
          <h3 className="text-sm font-semibold">היסטוריית גרסאות (לקריאה בלבד)</h3>
          <ul className="mt-3 space-y-4">
            {history.versions.map((termsVersion) => (
              <li key={termsVersion.id} className="border-b border-stone-100 pb-3 last:border-b-0">
                <div className="flex items-center gap-2 text-sm">
                  <span className="font-medium">גרסה {termsVersion.version}</span>
                  {history.current?.id === termsVersion.id && (
                    <span className="rounded bg-stone-800 px-2 py-0.5 text-xs text-white">
                      נוכחית
                    </span>
                  )}
                  <span className="text-xs text-stone-500">
                    {formatDate(termsVersion.created_at)}
                  </span>
                </div>
                <p className="mt-1 text-xs text-stone-600">
                  החזר עד {termsVersion.refundable_until_hours_before} שעות לפני · חילוט{" "}
                  {termsVersion.forfeit_percent}%
                </p>
                <p className="mt-1 whitespace-pre-wrap text-sm text-stone-700">
                  {termsVersion.terms_text}
                </p>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
