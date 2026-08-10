import { useState } from "react";
import type { ShiftTemplate } from "../api";
import { MyWeekPanel } from "./MyWeekPanel";
import { RosterPane } from "./RosterPane";
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
// retry, AND THE CONTAINER OWNS NONE. There is deliberately no shared "the
// section failed" state: a 500 on the templates read must not blank a
// submissions list that arrived fine, and a pane's `h2` survives both its
// loading and its failure render so the heading order never changes.
//
// ⚠ AND THE CONTAINER FETCHES NOTHING ITSELF, which is not a style choice. A
// container read gating the panes cost three things at once: a seamstress waited
// for `GET /shifts/templates` before `MyWeekPanel` even began `GET /shifts/week`
// — two sequential round-trips for the highest-volume user of this feature, on a
// value she never reads; an elevated mount issued the SAME templates request
// twice, once here and once in the pane; and because the container's copy never
// refetched, a successful seed never released §1.1's `if` and a first-run
// boutique stayed on one Card until somebody reloaded the page (§5.2 binds the
// opposite). `ShiftTemplatesPane` reads it, reports it, and this observes.

// Spelled locally, `FloorPanel.tsx:41` / `SeamstressPanel.tsx:35` /
// `AtelierSection.tsx:67`'s precedent — and the backend spells its twin locally
// too (`shifts/service.py`). Cosmetics only: the control is the server's gates.
const ELEVATED = new Set(["owner", "shift_manager"]);

export interface ShiftsSectionProps {
  /** Her role. Picks the pane set and the past-the-deadline wording. */
  role: string;
}

export function ShiftsSection({ role }: ShiftsSectionProps) {
  const elevated = ELEVATED.has(role);
  // `null` until `ShiftTemplatesPane` resolves its read — and for a
  // non-elevated staffer, forever: that pane never mounts for her, so nothing in
  // this section fetches templates on her behalf. Her own week payload already
  // carries the ones she needs, and §2.5-E1's empty state lives inside it.
  const [templates, setTemplates] = useState<ShiftTemplate[] | null>(null);

  // ⚠ FIRST RUN INVERTS THE ORDER EXACTLY ONCE. With no live template anywhere,
  // the other three panes have nothing to say — an empty week, an empty
  // readiness list, a deadline governing nothing — and three stacked empties
  // above the one button that fixes them is a first-run screen that hides its
  // own next step. One `if`, no new state.
  //
  // It keys on the RESOLVED read, so while that read is in flight an elevated
  // actor sees all four Cards' own skeletons and the collapse happens on the
  // response — never a flash of four empties, because none of them has rendered
  // content yet. A FAILED read leaves it `null` and collapses nothing.
  const firstRun = templates !== null && templates.length === 0;

  // ⚠ CONDITIONALS IN PLACE, NEVER AN EARLY RETURN. The three slots keep their
  // positions across the collapse, so `ShiftTemplatesPane` stays MOUNTED through
  // it — an early return would reconcile it against `MyWeekPanel` at index 0,
  // remount it, wipe the `shifts.seedDone` line and drop the focus destination
  // §5.2 names, on the one render where that matters most.
  return (
    <div className="flex flex-col gap-6">
      {!firstRun && <MyWeekPanel elevated={elevated} />}
      {elevated && !firstRun && (
        <>
          <WeekSubmissionsPane templates={templates ?? []} />
          {/* Readiness above the build, configuration below it — `ShiftsSection`'s
              stated ordering, unchanged. F40 D17: an elevated actor now sees FIVE
              `h2`s here, a non-elevated staffer still sees one. */}
          <RosterPane />
          <ShiftsDeadlineCard />
        </>
      )}
      {elevated && <ShiftTemplatesPane onTemplates={setTemplates} />}
    </div>
  );
}
