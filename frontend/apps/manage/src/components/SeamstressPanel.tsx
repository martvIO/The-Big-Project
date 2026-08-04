import { Fragment, useEffect, useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { Button, Card, cn } from "@boutique/ui";
import type { SeamstressRef } from "../api";
import { hoursFromMinutes, loadRatio, overloaded, sortByRemainingCapacity } from "../lib/capacity";
import { plainDate } from "../lib/jerusalem";

// The roster, its load bars and the two write triggers, inside F41's atelier
// section. A LIST and not a matrix: the epic's "capacity matrix" is F40's
// shape, whose second dimension is the roster projection this run drops, and
// with one weekly number per person there is one value per row.
//
// That also discharges the keyboard requirement STRUCTURALLY — there is no
// role="grid", no roving tabindex and no arrow-key manager anywhere in this
// feature, because a <ul> whose every row is text plus one ordinary Button
// needs none.

// AtelierSection's shipped set, restated rather than imported: that module
// imports this one, so exporting it from there would be a cycle, and lifting it
// to lib/ would edit a file this task does not own for one line. Both write
// controls gate on it.
//
// ⚠ THE GATE IS NOT COSMETICS. A seamstress is admitted to the board by the
// router and refused by both write routes, so a control she can tap produces a
// 403 → runMutation's catch → poll.fail → usePoll's {401,403} terminal rule →
// her ENTIRE atelier board is replaced by «אין הרשאה», because she tapped
// something this console offered her.
const ELEVATED = new Set(["owner", "shift_manager"]);

const HEADING_ID = "atelier-h-capacity";

// DashboardSection.tsx:21-44's widget, COPIED — not imported across sections
// and not promoted to packages/ui. The dashboard spec's D10 declined promotion,
// it is ten lines, and a cross-section component import is worse than a copy.
// Promotion is the recorded upgrade at a THIRD caller.
//
// `over` is the only argument added to the shipped signature, and it is
// `overloaded(row)` — the same predicate, from the same module, that sets the
// word beside it. One predicate, one place, three consumers: the colour, the
// word and the assign cue. That is what makes "overload is never colour-only" a
// structural property rather than a rule somebody has to remember — you cannot
// ship the colour without the word, because they read the same boolean.
function Bar({ pct, over }: { pct: number; over: boolean }) {
  // The clamp keeps a contract change from painting outside the track, and the
  // isFinite guard is the shipped Bar's own: `inline-size: NaN%` is an IGNORED
  // declaration that silently leaves the previous width in place on a
  // re-render, so on a five-second poll a bar could keep a stale width for a
  // whole shift with nothing on screen wrong. `loadRatio` already answers a
  // clamped, finite number; this is the widget's own line, kept verbatim.
  const size = Number.isFinite(pct) ? Math.min(Math.max(pct, 0), 100) : 0;
  return (
    // aria-hidden on the whole widget, so the fill goes with it. It is NEVER
    // role="progressbar": that role announces a task's progress, not a level,
    // and its honest form would need an aria-valuetext byte-identical to the
    // sentence beside it — one fact in the accessibility tree twice. Every
    // value this bar draws is text in the same row; remove every bar and the
    // panel loses nothing.
    <span aria-hidden="true" className="mt-2 block h-2 rounded-sm bg-border">
      {/* inlineSize, NEVER width — one spelling of one widget, and the form
          that stays correct if a writing mode ever changes. ⚠ The fill grows
          from the inline-start edge, which under the console's dir="rtl" is the
          PHYSICAL RIGHT — and that is dir="rtl"'s doing, not the logical
          property's. Nothing in this tree may introduce a `dir`. */}
      <span
        className={cn("block h-2 rounded-sm", over ? "bg-danger" : "bg-gold-strong")}
        style={{ inlineSize: `${size}%` }}
      />
    </span>
  );
}

export interface SeamstressPanelProps {
  seamstresses: SeamstressRef[];
  // ⚠ The UNFILTERED sum: no bar means no rate, so there is nothing to narrow
  // to a week, and «בתור» on the seamstress rows already means this quantity.
  unassignedMinutes: number;
  // The server's own horizon, off the envelope. The client cannot compute it —
  // lib/jerusalem.ts ships zero date arithmetic, and a browser that has crossed
  // Jerusalem midnight would print a date the SQL never filtered on.
  dueSoonThrough: string;
  role: string;
  // C7: AtelierSection's deferred terminal gates on `dialogOpen`, and the
  // panel's dialogs live here where the section cannot see them. Without the
  // signal a 401 tick unmounts a settings dialog holding six edited band
  // values.
  onDialogOpenChange: (open: boolean) => void;
}

export function SeamstressPanel({
  seamstresses,
  unassignedMinutes,
  dueSoonThrough,
  role,
  onDialogOpenChange,
}: SeamstressPanelProps) {
  const { t } = useTranslation();
  const elevated = ELEVATED.has(role);
  // The two dialogs mount at PANEL level — siblings of the <ul>, never inside
  // an <li>: a repaint that removed the row would unmount a dialog mounted
  // inside it and discard what she typed. The state lives here for that reason;
  // the dialogs themselves are the next task, and the C7 signal below is what
  // reads it today.
  const [capacityTarget, setCapacityTarget] = useState<SeamstressRef | null>(null);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const dialogOpen = capacityTarget !== null || settingsOpen;

  // Reported on CHANGE and in BOTH directions, from the state itself rather
  // than from each trigger: a dialog dismissed by Esc or by the backdrop never
  // passes through a handler here, and a signal that only ever went `true`
  // would leave the section's terminal deferred forever.
  useEffect(() => {
    onDialogOpenChange(dialogOpen);
  }, [dialogOpen, onDialogOpenChange]);

  const rows = sortByRemainingCapacity(seamstresses);

  return (
    <section aria-labelledby={HEADING_ID} className="space-y-2">
      {/* F41's column-heading shape exactly. tabIndex={-1} adds NO tab stop —
          it is a focus TARGET for a save whose trigger has unmounted. The
          COUNTED string, because the count is what tells a screen-reader user
          the list is long before she enters it. */}
      <h3 id={HEADING_ID} tabIndex={-1} className="text-base font-semibold text-ink">
        {t("atelier.capacity.headingCount", { total: seamstresses.length })}
      </h3>
      {/* ONE Card around a divide-y list, the INVERSE of F41's per-ticket Card,
          and the reason is one sentence: a seamstress row moves nowhere. F41
          made the ticket the Card because the unit of that screen is a thing
          that moves between named regions; a roster row is a static line about
          a person, and three stacked Cards above five columns of Cards is
          shadow-sm on shadow-sm. `p-6` is untouched — cn() is a plain join and
          the consumer loses. */}
      <Card className="space-y-3">
        {rows.length === 0 ? (
          // ⚠ TWO STRINGS, NOT ONE. The staff screen is owner-only, and a line
          // telling a shift manager to go somewhere the gate refuses is this
          // console lying about its own permissions.
          <p className="text-sm text-ink-muted">
            {t(role === "owner" ? "atelier.capacity.emptyOwner" : "atelier.capacity.empty")}
          </p>
        ) : (
          // ⚠ tabIndex={0} UNCONDITIONALLY even though the overflow is md:-only:
          // axe's scrollable-region-focusable fires on exactly this shape, and a
          // resize observer deciding an ARIA-relevant attribute is a mechanism
          // to keep true for a tab stop that costs nothing. It is also the
          // keyboard's entry stop into the list, and a NAMED list announces
          // «תופרות, רשימה, 3 פריטים» when focused.
          //
          // ⚠ The name is the UNCOUNTED key: an accessible name must not churn
          // on a five-second tick, and this count can change with no staff edit
          // at all.
          //
          // Bounded at ≥768 ONLY. Bounding at 375 reintroduces the scroll-trap
          // F41 refused on the primary device, and 24 rem — not a viewport unit
          // — is stable across viewports and honours the root text scale.
          <ul
            tabIndex={0}
            aria-label={t("atelier.capacity.heading")}
            className="divide-y divide-border md:max-h-96 md:overflow-y-auto"
          >
            {rows.map((row) => (
              <Row
                key={row.id}
                row={row}
                dueSoonThrough={dueSoonThrough}
                elevated={elevated}
                onEdit={setCapacityTarget}
              />
            ))}
          </ul>
        )}
        {/* A SIBLING of the </ul>, never an <li>: `{{total}}` in the heading is
            PEOPLE, and with this line inside the list a screen-reader user
            would hear «תופרות, 4 פריטים» after a heading claiming 3. It carries
            no bar — nobody has capacity for it, so there is no denominator and a
            bar would be a ratio to nothing. Rendered only above zero: a zero
            line is noise on every board that is fully assigned. */}
        {unassignedMinutes > 0 && (
          <p className="text-sm text-ink-muted">
            {t("atelier.capacity.unassignedRow", { hours: hoursFromMinutes(unassignedMinutes) })}
          </p>
        )}
        {/* At the panel's FOOT and therefore the LAST stop in it: a
            boutique-wide configuration used once a quarter must not sit above
            the rows a manager opens the panel to read, pushing every one of
            them a stop further away. It renders on an empty panel too — the
            ruler is worth setting before the first hire. */}
        {elevated && (
          <Button
            variant="ghost"
            size="md"
            fullWidthMobile={false}
            aria-label={t("atelier.settings.openAria")}
            onClick={() => setSettingsOpen(true)}
          >
            {t("atelier.settings.open")}
          </Button>
        )}
      </Card>
    </section>
  );
}

function Row({
  row,
  dueSoonThrough,
  elevated,
  onEdit,
}: {
  row: SeamstressRef;
  dueSoonThrough: string;
  elevated: boolean;
  onEdit: (row: SeamstressRef) => void;
}) {
  const { t } = useTranslation();
  const pct = loadRatio(row);
  const over = overloaded(row);

  // The clauses, in this order and no other, joined by « · »:
  //   {load | loadNoCapacity + notSet}  [· over]  [· backlog]  [· fromDefault]
  // The alarm as early as the grammar allows, the qualifier last. A
  // screen-reader user hears them in order and a manager scanning three rows
  // reads the first half of each.
  const clauses: ReactNode[] = [];
  if (row.weekly_capacity_hours === null) {
    // ⚠ `{{hours}}` is her WHOLE BACKLOG here and not the seven-day slice:
    // there is no bar, so there is no horizon to divide into, and the backlog
    // is what makes an unconfigured row comparable with a configured one's
    // «בתור» clause.
    clauses.push(t("atelier.capacity.loadNoCapacity", { hours: hoursFromMinutes(row.assigned_minutes) }));
    clauses.push(t("atelier.capacity.notSet"));
  } else {
    clauses.push(
      t("atelier.capacity.load", {
        hours: hoursFromMinutes(row.due_soon_minutes),
        // A wire `datetime.date`, split on `-`. NEVER through a Date: that
        // parses as UTC midnight and running it through a zoned formatter
        // re-zones a date that was never in a zone.
        date: plainDate(dueSoonThrough),
        capacity: row.weekly_capacity_hours,
      }),
    );
    if (over) {
      // ⚠ A <strong> INSIDE THE ONE <p>, never a second Badge: F41 fixes
      // exactly one Badge per card and overdue owns it, and a Badge here would
      // split the payload into two announced chunks. `text-danger` on
      // `bg-surface` is 6.18:1, so the word passes AA as text on its own, and
      // `font-semibold` is the non-colour half.
      clauses.push(
        <strong key="over" className="font-semibold text-danger">
          {t("atelier.capacity.over")}
        </strong>,
      );
    }
    // Only when the bar's week is hiding some of it. The clause exists so the
    // total is never hidden behind the seven-day slice; when the slice IS the
    // total it would state one number twice, which is why none of the deck's
    // five bar renderings carries it and the worked row (360 due, 720 held)
    // does.
    if (row.assigned_minutes > row.due_soon_minutes) {
      clauses.push(t("atelier.capacity.backlog", { hours: hoursFromMinutes(row.assigned_minutes) }));
    }
    if (row.capacity_is_default) {
      // Last, because it qualifies WHOSE the denominator is rather than whether
      // there is a problem — and it is never rendered when she has her own
      // hours.
      clauses.push(t("atelier.capacity.fromDefault"));
    }
  }
  if (!row.assignable) {
    // The shipped word, from the same `assignable` flag the card reads. Last,
    // and inside the same <p>, so the row still announces as ONE sentence.
    clauses.push(t("atelier.assigneeInactive"));
  }

  return (
    <li data-seamstress-id={row.id} className="py-3 first:pt-0 last:pb-0">
      {/* flex-wrap so a long name pushes the button to the next line rather
          than squeezing it — F41's name/Badge rule, at a different pair. */}
      <div className="flex flex-wrap items-center justify-between gap-2">
        {/* A BARE <bdi>, never isolateLtr: that helper emits
            <bdi dir="ltr">, and forcing LTR on «נועה לוי» reverses its Hebrew
            words — a bidi defect that looks deliberate, which is the kind
            nobody files. */}
        <bdi className="font-semibold text-ink break-words">{row.display_name}</bdi>
        {/* Absent for a non-elevated viewer AND on a row the server would
            refuse: `_require_seamstress` rejects a retired or re-roled staffer,
            and rendering a control that always 400s is a trap. */}
        {elevated && row.assignable && (
          <Button
            variant="ghost"
            size="md"
            fullWidthMobile={false}
            aria-label={t("atelier.capacity.editAria", { name: row.display_name })}
            onClick={() => onEdit(row)}
          >
            {t("atelier.capacity.edit")}
          </Button>
        )}
      </div>
      {/* ABSENT — not empty — when no capacity is resolved. An empty track says
          "she has room and holds nothing"; NO track says "nobody has told this
          product how much she can take." A bar against an invented denominator
          is a picture of a number that does not exist. */}
      {pct !== null && <Bar pct={pct} over={over} />}
      {/* THE PAYLOAD. Real text in the DOM, read by everyone, in the same words
          a sighted user reads. Never truncated, never clamped, never
          abbreviated — and NO bidi helper: every numeral is bracketed by
          Hebrew, which is what makes the runs resolve in place under the bidi
          algorithm, and `isolateLtr` isolates ONE run by indexOf, so on
          «12.1 … מתוך 12» it would wrap a fragment of the wrong number. */}
      <p className="mt-1 text-sm text-ink-muted">
        {/* A Fragment and not a wrapper <span>: the row must announce as ONE
            continuous sentence, and every clause in it comes from the bundle. */}
        {clauses.map((clause, index) => (
          <Fragment key={index}>
            {index > 0 ? " · " : ""}
            {clause}
          </Fragment>
        ))}
      </p>
    </li>
  );
}
