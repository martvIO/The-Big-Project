import { Fragment, useEffect, useRef, useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { Button, Card, cn, Input, Modal } from "@boutique/ui";
import type { AtelierSettingsUpdate, EffortBand, EffortBandRef, SeamstressRef } from "../api";
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

// The band's OWN word, keyed by the wire's band key.
//
// ⚠ NOT `bandLabel(minutes, bands, t)`, which is a FIRST-MATCH-WINS REVERSE
// LOOKUP BY MINUTES — and this very dialog is what makes two bands share a
// number: the server forbids neither duplicates nor an increasing order, and
// §4.2 says so explicitly. Labelled that way, an owner who flattens «יום מלא»
// onto «חצי יום»'s 240 gets TWO fields both called «חצי יום — דקות» and edits
// the wrong one.
//
// ⚠ AND IT IS RESTATED HERE RATHER THAN EXPORTED FROM `lib/stages.ts`, whose
// private `BAND_KEY_SUFFIX` is the same five rows: that file is under the
// scope fence and must diff empty against `origin/main`. A `Record<EffortBand,
// string>` is what keeps the restatement honest — a sixth band added to the
// union without a row here is a COMPILE error, never a field rendering its own
// key.
const BAND_LABEL_KEY: Record<EffortBand, string> = {
  thirty_min: "atelier.band.thirtyMin",
  one_hour: "atelier.band.oneHour",
  two_hours: "atelier.band.twoHours",
  half_day: "atelier.band.halfDay",
  full_day: "atelier.band.fullDay",
};

// A whole non-negative number, and nothing else. ⚠ The client refuses the
// SHAPE; the SERVER states the range — 0..168 for hours and 1..1440 for
// minutes are CHECK constraints, and a client that mirrored either would be one
// migration away from lying with nothing to catch it
// (`test_frontend_constant_parity.py` scrapes only the two validation.ts files).
const WHOLE_NUMBER = /^\d+$/;

/** `null` for an empty field — the value that CLEARS — or `false` for a refusal. */
function wholeOrEmpty(raw: string): number | null | false {
  const trimmed = raw.trim();
  if (trimmed === "") {
    return null;
  }
  return WHOLE_NUMBER.test(trimmed) ? Number(trimmed) : false;
}

/** A band's minutes: whole and strictly positive. Empty is a refusal, not a clear. */
function positiveWhole(raw: string): number | false {
  const trimmed = raw.trim();
  if (!WHOLE_NUMBER.test(trimmed)) {
    return false;
  }
  const value = Number(trimmed);
  return value > 0 ? value : false;
}

type BandDraft = Record<EffortBand, string>;

function bandDraftOf(bands: EffortBandRef[]): BandDraft {
  // Seeded from the platform's five so the record is TOTAL even if a payload
  // ever arrives short — an unkeyed field would render `value={undefined}` and
  // flip React to an uncontrolled input mid-dialog.
  const draft: BandDraft = {
    thirty_min: "",
    one_hour: "",
    two_hours: "",
    half_day: "",
    full_day: "",
  };
  for (const band of bands) {
    draft[band.band] = String(band.minutes);
  }
  return draft;
}

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
  // The tenant's own number, off the same envelope. `null` is a REAL answer —
  // the state every boutique is in on day one — and it is what decides between
  // the capacity dialog's two help lines and whether its clear control exists
  // at all.
  defaultCapacityHours: number | null;
  // The RESOLVED mapping, off the envelope, so the settings dialog opens with
  // no read of its own. A `GET /manage/settings` on open was considered and
  // refused: it buys five seconds off a staleness window whose real length is
  // however long the dialog stays open, which is minutes.
  bands: EffortBandRef[];
  // ⚠ BOTH RESOLVE AND NEITHER REJECTS. A rejecting promise would make this
  // panel duplicate `runMutation`'s catch and put a second `poll.fail` call
  // site in the feature — and there is no error OBJECT here to leak, which is
  // what makes «the server's English never reaches this Hebrew console»
  // structural rather than a `default:` branch somebody has to remember.
  onSaveCapacity: (staffUserId: string, hours: number | null) => Promise<boolean>;
  onSaveAtelierSettings: (patch: AtelierSettingsUpdate) => Promise<boolean>;
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
  defaultCapacityHours,
  bands,
  onSaveCapacity,
  onSaveAtelierSettings,
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

  const [hoursDraft, setHoursDraft] = useState("");
  const [hoursError, setHoursError] = useState<string | null>(null);
  const [capacityAlert, setCapacityAlert] = useState<string | null>(null);
  const [capacitySaving, setCapacitySaving] = useState(false);

  const [bandDraft, setBandDraft] = useState<BandDraft>(() => bandDraftOf(bands));
  const [defaultDraft, setDefaultDraft] = useState("");
  const [bandErrors, setBandErrors] = useState<Partial<Record<EffortBand, string>>>({});
  const [defaultError, setDefaultError] = useState<string | null>(null);
  const [settingsAlert, setSettingsAlert] = useState<string | null>(null);
  const [settingsSaving, setSettingsSaving] = useState(false);

  const headingRef = useRef<HTMLHeadingElement>(null);
  const capacityAlertRef = useRef<HTMLParagraphElement>(null);
  const settingsAlertRef = useRef<HTMLParagraphElement>(null);
  // ⚠ MONOTONIC, and the restore below is keyed on IT and never on the payload:
  // a state setter bails out of a reference-identical value, so keying on the
  // data would silently skip the one repaint the guard is waiting for.
  const [saveCount, setSaveCount] = useState(0);

  // Reported on CHANGE and in BOTH directions, from the state itself rather
  // than from each trigger: a dialog dismissed by Esc or by the backdrop never
  // passes through a handler here, and a signal that only ever went `true`
  // would leave the section's terminal deferred forever.
  useEffect(() => {
    onDialogOpenChange(dialogOpen);
  }, [dialogOpen, onDialogOpenChange]);

  useEffect(() => {
    // ⚠ THE ONE FOCUS DESTINATION, AND BOTH DIRECTIONS ARE PINNED BY THIS ONE
    // LINE. A seamstress leaves the `seamstresses` union the moment she is
    // retired AND her last undelivered ticket is delivered; if that repaint
    // lands between opening the dialog and saving, the trigger has unmounted
    // and native <dialog>'s auto-restore drops focus to <body>. This heading is
    // where she goes instead.
    //
    // And the `=== document.body` test is what stops the fix becoming a focus
    // STEAL in the other direction: it is the BROWSER saying the repaint
    // dropped focus, rather than this component guessing. F41 shipped the naive
    // version and an adversarial verifier caught the steal after it went green.
    //
    // ⚠ NO COMMIT STAMP, and adding one would be machinery for a race this
    // shape does not have. F41's restore fires on POLL repaints, which arrive
    // with no user action and can outlive the user's own focus move; this fires
    // only on a SUCCESSFUL SAVE, in the same turn, and only when focus is
    // already nowhere. Copying F41's mechanism wholesale is the obvious wrong
    // move.
    if (saveCount === 0) {
      return;
    }
    if (document.activeElement === document.body) {
      headingRef.current?.focus();
    }
  }, [saveCount]);

  const rows = sortByRemainingCapacity(seamstresses);

  const openCapacity = (row: SeamstressRef) => {
    // ⚠ THE ANTI-CONVERSION PREFILL. Her own number when it IS hers, EMPTY when
    // it is inherited — so saving without typing cannot silently convert a
    // number nobody chose into a number that is hers, after which raising the
    // boutique's default never reaches her again with no visible act anywhere.
    setHoursDraft(
      row.capacity_is_default || row.weekly_capacity_hours === null
        ? ""
        : String(row.weekly_capacity_hours),
    );
    setHoursError(null);
    setCapacityAlert(null);
    setCapacityTarget(row);
  };

  const openSettings = () => {
    setBandDraft(bandDraftOf(bands));
    setDefaultDraft(defaultCapacityHours === null ? "" : String(defaultCapacityHours));
    setBandErrors({});
    setDefaultError(null);
    setSettingsAlert(null);
    setSettingsOpen(true);
  };

  const submitCapacity = async (target: SeamstressRef) => {
    const hours = wholeOrEmpty(hoursDraft);
    if (hours === false) {
      setHoursError(t("atelier.capacity.error.hours"));
      return;
    }
    setHoursError(null);
    setCapacityAlert(null);
    setCapacitySaving(true);
    const ok = await onSaveCapacity(target.id, hours);
    setCapacitySaving(false);
    if (!ok) {
      // The dialog STAYS OPEN and the alert owns focus — a refusal that closed
      // the form would throw away what she typed and leave her guessing.
      setCapacityAlert(t("atelier.capacity.error.server"));
      return;
    }
    setCapacityTarget(null);
    setSaveCount((count) => count + 1);
  };

  const submitSettings = async () => {
    const minutes: Partial<Record<EffortBand, number>> = {};
    const errors: Partial<Record<EffortBand, string>> = {};
    for (const key of Object.keys(bandDraft) as EffortBand[]) {
      const value = positiveWhole(bandDraft[key]);
      if (value === false) {
        errors[key] = t("atelier.settings.error.minutes");
      } else {
        minutes[key] = value;
      }
    }
    const fallback = wholeOrEmpty(defaultDraft);
    setBandErrors(errors);
    setDefaultError(fallback === false ? t("atelier.settings.error.default") : null);
    if (Object.keys(errors).length > 0 || fallback === false) {
      return;
    }
    setSettingsAlert(null);
    setSettingsSaving(true);
    // ⚠ THE WHOLE BLOCK, BOTH KEYS, ALWAYS. `merge_settings` is one atomic
    // `settings = settings || :patch::jsonb` and `||` merges at the TOP LEVEL
    // ONLY, so a patch carrying a PARTIAL `atelier` object replaces the key and
    // deletes what it did not name.
    const ok = await onSaveAtelierSettings({
      effort_bands: minutes as Record<EffortBand, number>,
      default_weekly_capacity_hours: fallback,
    });
    setSettingsSaving(false);
    if (!ok) {
      setSettingsAlert(t("atelier.settings.error.server"));
      return;
    }
    setSettingsOpen(false);
    setSaveCount((count) => count + 1);
  };

  useEffect(() => {
    if (capacityAlert !== null) {
      capacityAlertRef.current?.focus();
    }
  }, [capacityAlert]);

  useEffect(() => {
    if (settingsAlert !== null) {
      settingsAlertRef.current?.focus();
    }
  }, [settingsAlert]);

  return (
    <section aria-labelledby={HEADING_ID} className="space-y-2">
      {/* F41's column-heading shape exactly. tabIndex={-1} adds NO tab stop —
          it is a focus TARGET for a save whose trigger has unmounted. The
          COUNTED string, because the count is what tells a screen-reader user
          the list is long before she enters it. */}
      <h3 ref={headingRef} id={HEADING_ID} tabIndex={-1} className="text-base font-semibold text-ink">
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
                onEdit={openCapacity}
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
            onClick={openSettings}
          >
            {t("atelier.settings.open")}
          </Button>
        )}
      </Card>

      {/* ⚠ BOTH DIALOGS AT PANEL LEVEL — siblings of the </Card>, NEVER inside
          an <li>. F41's C6 rule forbids the <li> and nothing further: a repaint
          that removed the row would unmount a dialog mounted inside it and
          discard what she typed — and the repaint that removes a row arrives
          every five seconds with no user action at all. Any «section level»
          reading is wrong too: the dialogs need this component's state and this
          component's heading ref. */}
      <Modal
        open={capacityTarget !== null}
        onClose={() => setCapacityTarget(null)}
        title={t("atelier.capacity.dialogTitle")}
        footer={
          /* EXACTLY TWO. `Modal.tsx:54` is `mt-6 flex justify-end gap-3` —
             hard-coded, no flex-wrap, no className seam — and three buttons,
             one of them five Hebrew words, overflow the 295 px of dialog
             content at 375. Editing packages/ui from a call site is barred, so
             «חזרה לברירת המחדל» lives in the BODY and CLEARS the field. */
          <>
            <Button
              type="button"
              variant="ghost"
              size="md"
              fullWidthMobile={false}
              onClick={() => setCapacityTarget(null)}
            >
              {t("atelier.form.cancel")}
            </Button>
            <Button
              type="button"
              variant="primary"
              size="md"
              fullWidthMobile={false}
              loading={capacitySaving}
              onClick={() => {
                if (capacityTarget !== null) {
                  void submitCapacity(capacityTarget);
                }
              }}
            >
              {t("atelier.capacity.submit")}
            </Button>
          </>
        }
      >
        {capacityTarget !== null && (
          <div className="space-y-3 text-start">
            <Input
              label={t("atelier.capacity.hoursLabel")}
              /* ⚠ TWO help strings, because one of them would be a LIE on every
                 boutique on day one — the state D2 says every boutique starts
                 in. The number is the TENANT's, so she can see what she is
                 falling back TO. */
              help={
                defaultCapacityHours === null
                  ? t("atelier.capacity.hoursHelpNoDefault")
                  : t("atelier.capacity.hoursHelp", { hours: defaultCapacityHours })
              }
              type="number"
              inputMode="numeric"
              min={0}
              /* ⚠ NO `max`. 168 is MAX_WEEKLY_CAPACITY_HOURS — a SERVER bound —
                 and mirroring it here would have none of the protection a
                 mirrored constant gets: `test_frontend_constant_parity.py`
                 scrapes only the two validation.ts files, so raising the CHECK
                 would leave this attribute lying, silently and greenly. The
                 shape is the client's; the range is the server's 400.

                 ⚠ And NO `dir="ltr"`, which the phone field carries because it
                 holds `+`, `-` and spaces — NEUTRALS that reorder at an RTL
                 boundary. A bare integer is one uninterrupted EN run. */
              value={hoursDraft}
              error={hoursError ?? undefined}
              onChange={(event) => setHoursDraft(event.target.value)}
            />
            {/* Rendered whenever the tenant HAS a default, and NOT conditioned
                on the field being non-empty: a control that appears and
                disappears as she types is a control that moves under her
                finger. On an already-empty field it is a harmless no-op tap. */}
            {defaultCapacityHours !== null && (
              <Button
                type="button"
                variant="ghost"
                size="md"
                fullWidthMobile={false}
                onClick={() => {
                  setHoursDraft("");
                  setHoursError(null);
                }}
              >
                {t("atelier.capacity.useDefault")}
              </Button>
            )}
            {capacityAlert !== null && (
              <p
                ref={capacityAlertRef}
                role="alert"
                tabIndex={-1}
                className="text-sm text-danger"
              >
                {capacityAlert}
              </p>
            )}
          </div>
        )}
      </Modal>

      <Modal
        open={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        title={t("atelier.settings.title")}
        footer={
          <>
            <Button
              type="button"
              variant="ghost"
              size="md"
              fullWidthMobile={false}
              onClick={() => setSettingsOpen(false)}
            >
              {t("atelier.form.cancel")}
            </Button>
            <Button
              type="button"
              variant="primary"
              size="md"
              fullWidthMobile={false}
              loading={settingsSaving}
              onClick={() => void submitSettings()}
            >
              {t("atelier.settings.submit")}
            </Button>
          </>
        }
      >
        {/* ⚠ NO `max-h-[80vh] overflow-y-auto` here or on Modal:
            `<dialog:modal>`'s UA stylesheet already supplies
            `max-height: calc(100% - 6px - 2em)` and `overflow: auto`, so six
            number fields scroll natively on a short viewport. Adding it would
            be a packages/ui edit for a behaviour the platform provides, and it
            would change every dialog in both apps. */}
        <div className="space-y-3 text-start">
          <p className="text-sm font-semibold text-ink">{t("atelier.settings.bandsLabel")}</p>
          {/* ⚠ F-11 — D4's consequence, said out loud. A re-tune re-values
              nothing (there is no `effort_band` column; the minutes persist),
              which means an OLD CARD SILENTLY RELABELS: flattening «יום מלא»
              from 480 to 240 makes every garment ever estimated at «חצי יום»
              read «יום מלא» on the board, with no fallback and no visible act.
              Without this line an owner correcting one band gets an unexplained
              relabel across her board and no way to connect the two. */}
          <p className="text-xs text-ink-muted">{t("atelier.settings.bandsHelp")}</p>
          {bands.map((band) => (
            <Input
              key={band.band}
              label={t("atelier.settings.bandMinutes", { band: t(BAND_LABEL_KEY[band.band]) })}
              type="number"
              inputMode="numeric"
              min={1}
              value={bandDraft[band.band]}
              error={bandErrors[band.band]}
              onChange={(event) =>
                setBandDraft((current) => ({ ...current, [band.band]: event.target.value }))
              }
            />
          ))}
          <Input
            label={t("atelier.settings.defaultCapacity")}
            help={t("atelier.settings.defaultCapacityHelp")}
            type="number"
            inputMode="numeric"
            min={0}
            value={defaultDraft}
            error={defaultError ?? undefined}
            onChange={(event) => setDefaultDraft(event.target.value)}
          />
          {settingsAlert !== null && (
            <p ref={settingsAlertRef} role="alert" tabIndex={-1} className="text-sm text-danger">
              {settingsAlert}
            </p>
          )}
        </div>
      </Modal>
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
