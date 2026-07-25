import { useCallback, useEffect, useState } from "react";
import type { FormEvent } from "react";
import { Badge, Button, Card, Input, Skeleton, TextArea } from "@boutique/ui";
import { api, errorMessage } from "../api";
import type { TermsHistory } from "../api";
import { validateTerms } from "../validation";

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
      // v1 shows only the latest page (50 versions); the API supports offset
      // paging when a deeper history view is needed.
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
    return (
      <p role="alert" className="text-sm text-ink-muted">
        {loadError}
      </p>
    );
  }
  if (history === null) {
    return <Skeleton variant="text" lines={4} />;
  }

  const hasPolicy = history.versions.length > 0;

  return (
    <div className="space-y-6">
      {!hasPolicy && (
        <div
          data-testid="terms-setup-blocker"
          className="rounded-md border border-gold-strong bg-surface p-4"
        >
          <h3 className="text-base font-semibold text-warning-text">
            עדיין לא הוגדרה מדיניות ביטולים
          </h3>
          <p className="mt-1 text-sm text-warning-text">
            לא ניתן לקבל הזמנות ללא מדיניות ביטולים פעילה — כל הזמנה מחייבת אישור תקנון. יש
            ליצור גרסה ראשונה למטה כדי להשלים את הקמת הבוטיק.
          </p>
        </div>
      )}

      {history.current !== null && (
        <Card>
          <h3 className="text-sm font-semibold">
            גרסה נוכחית: {history.current.version}
          </h3>
          <p className="mt-1 text-sm text-ink-muted">
            החזר מלא עד {history.current.refundable_until_hours_before} שעות לפני התור · חילוט{" "}
            {history.current.forfeit_percent}% מהמקדמה מחוץ לחלון
          </p>
        </Card>
      )}

      <Card>
        <form onSubmit={(event) => void handleSubmit(event)} className="flex flex-col gap-4">
          <h3 className="text-sm font-semibold">יצירת גרסה חדשה</h3>
          <p className="text-xs text-ink-muted">
            כל שמירה יוצרת גרסה חדשה וקבועה — גרסאות קודמות נשמרות לעד ואינן ניתנות לעריכה.
          </p>
          <div className="grid gap-4 sm:grid-cols-2">
            <Input
              label="החזר מלא עד (שעות לפני התור)"
              type="number"
              min={0}
              value={refundHours}
              onChange={(event) => setRefundHours(event.target.value)}
            />
            <Input
              label="אחוז חילוט מחוץ לחלון"
              type="number"
              min={0}
              max={100}
              value={forfeitPercent}
              onChange={(event) => setForfeitPercent(event.target.value)}
            />
          </div>
          <TextArea
            label="תוכן מדיניות הביטולים"
            rows={6}
            value={termsText}
            onChange={(event) => setTermsText(event.target.value)}
          />
          {formError !== null && (
            <p role="alert" className="text-sm text-danger">
              {formError}
            </p>
          )}
          <Button type="submit" loading={saving}>
            שמירת גרסה חדשה
          </Button>
        </form>
      </Card>

      {hasPolicy && (
        <Card>
          <h3 className="text-sm font-semibold">היסטוריית גרסאות (לקריאה בלבד)</h3>
          <ul className="mt-3 space-y-4">
            {history.versions.map((termsVersion) => (
              <li key={termsVersion.id} className="border-b border-border pb-3 last:border-b-0">
                <div className="flex items-center gap-2 text-sm">
                  <span className="font-medium">גרסה {termsVersion.version}</span>
                  {history.current?.id === termsVersion.id && (
                    <Badge variant="gold">נוכחית</Badge>
                  )}
                  <span className="text-xs text-ink-muted">
                    {formatDate(termsVersion.created_at)}
                  </span>
                </div>
                <p className="mt-1 text-xs text-ink-muted">
                  החזר עד {termsVersion.refundable_until_hours_before} שעות לפני · חילוט{" "}
                  {termsVersion.forfeit_percent}%
                </p>
                <p className="mt-1 whitespace-pre-wrap text-sm text-ink">
                  {termsVersion.terms_text}
                </p>
              </li>
            ))}
          </ul>
        </Card>
      )}
    </div>
  );
}
