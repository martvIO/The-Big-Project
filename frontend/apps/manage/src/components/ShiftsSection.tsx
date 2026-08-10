import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Button, Card, Skeleton } from "@boutique/ui";
import { api } from "../api";
import type { ShiftTemplate } from "../api";
import { MyWeekPanel } from "./MyWeekPanel";
import { ShiftTemplatesPane } from "./ShiftTemplatesPane";
import { ShiftsDeadlineCard } from "./ShiftsDeadlineCard";
import { WeekSubmissionsPane } from "./WeekSubmissionsPane";

// The seventeenth console section, reachable by all five staff roles, with four
// panes behind one nav row.
//
// ⚠ THE PANE ORDER IS HER WEEK FIRST, FOR EVERY ROLE. One mental model, one e2e
// path — and an owner who has to scroll past a list she reads first is an owner
// who stops answering her own week. Configuration last: the readiness read is
// the recurring elevated act, the deadline and the templates are the once-ever
// block, which is `HoursSection`'s shape.
//
// ⚠ EACH PANE OWNS ITS OWN READ, ITS OWN SKELETON AND ITS OWN `role="alert"` +
// retry. There is deliberately no shared "the section failed" state: a 500 on the
// templates read must not blank a submissions list that arrived fine, and a
// pane's `h2` survives both its loading and its failure render so the heading
// order never changes.

// Spelled locally, `FloorPanel.tsx:41` / `SeamstressPanel.tsx:35` /
// `AtelierSection.tsx:67`'s precedent — and the backend spells its twin locally
// too (`shifts/service.py`). Cosmetics only: the control is the server's gates.
const ELEVATED = new Set(["owner", "shift_manager"]);

export interface ShiftsSectionProps {
  /** Her role. Picks the pane set and the past-the-deadline wording. */
  role: string;
}

export function ShiftsSection({ role }: ShiftsSectionProps) {
  const { t } = useTranslation();
  const elevated = ELEVATED.has(role);
  const [templates, setTemplates] = useState<ShiftTemplate[] | null>(null);
  const [loadFailed, setLoadFailed] = useState(false);

  const load = useCallback(async () => {
    setLoadFailed(false);
    try {
      setTemplates((await api.listShiftTemplates()).templates);
    } catch {
      setTemplates(null);
      setLoadFailed(true);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  // ⚠ FIRST RUN INVERTS THE ORDER EXACTLY ONCE. With no live template anywhere,
  // the other three panes have nothing to say — an empty week, an empty
  // readiness list, a deadline governing nothing — and three stacked empties
  // above the one button that fixes them is a first-run screen that hides its
  // own next step. One `if`, no new state.
  //
  // It keys on the RESOLVED read, so while that read is in flight an elevated
  // actor sees the panes' own skeletons and the collapse happens on the response
  // — never a flash of four empties.
  const firstRun = templates !== null && templates.length === 0;

  if (templates === null) {
    return (
      <div className="flex flex-col gap-6">
        <Card>
          <h2 className="text-xl font-semibold text-ink">{t("shifts.myWeekHeading")}</h2>
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
      </div>
    );
  }

  if (firstRun && elevated) {
    return (
      <div className="flex flex-col gap-6">
        <ShiftTemplatesPane />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <MyWeekPanel elevated={elevated} />
      {elevated && (
        <>
          <WeekSubmissionsPane templates={templates} />
          <ShiftsDeadlineCard />
          <ShiftTemplatesPane />
        </>
      )}
    </div>
  );
}
