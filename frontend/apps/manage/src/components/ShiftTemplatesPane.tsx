import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Button, Card, EmptyState, Input, Modal, Select, Skeleton, TimeField } from "@boutique/ui";
import { api, ApiError, errorMessage } from "../api";
import type { ShiftTemplate, ShiftTemplateInput, StaffRole } from "../api";
import { DAY_NAMES } from "../lib/week";
import { MAX_TEMPLATES_PER_DAY, validateShiftTemplate } from "../validation";

// The owner's shift editor (elevated only). ONE Card with seven hairline-
// separated weekday sections — NOT seven Cards: seven `p-6` boxes is 336px of
// padding alone inside a 720px column, which is the shape F35 §2 already ruled
// out («20 cards in a 448px dialog is a scroll of chrome»).
//
// ⚠ SATURDAY RENDERS, EMPTY. It has no `availability_rules` row for almost every
// boutique, so the seed makes no template for it — and hiding the day would make
// that absence look like a bug rather than the tenant's own data (D3). A boutique
// that does open on Saturday gets the same add button as every other day.

const MAPPED_CODES: Record<string, string> = {
  TEMPLATES_ALREADY_SEEDED: "shifts.errors.alreadySeeded",
  NO_OPENING_HOURS: "shifts.seedNoHours",
  TEMPLATE_LIMIT_REACHED: "shifts.dayLimitReached",
  NOT_AUTHORIZED: "shifts.errors.notAuthorized",
  NOT_FOUND: "shifts.errors.notFound",
};

const hhmm = (time: string) => time.slice(0, 5);
const hhmmss = (time: string) => (time.length === 5 ? `${time}:00` : time);

interface Draft {
  // `null` while adding — there is no row yet.
  id: string | null;
  dayOfWeek: number;
  label: string;
  startsAtTime: string;
  endsAtTime: string;
  // Resent verbatim on a PATCH: D2 is a FULL REPLACE of all five fields, and the
  // console never shows this one (the list orders by
  // `(day, sort_order, starts_at_time)` and a manual order box on a two-item
  // list is a control nobody wants).
  sortOrder: number;
  // ⚠ F40 D10, AND SEEDED FROM THE ROW. The PATCH is a FULL REPLACE, so a draft
  // that did not carry the existing targets would silently CLEAR them on every
  // unrelated label edit — which is the exact silent loss D2's full-replace rule
  // exists to prevent, arriving through the one control that writes them.
  //
  // Held as STRINGS, one per role, because `""` and `"0"` are different values:
  // empty omits the key entirely («no target») and `0` writes a zero
  // («deliberately nobody»). A `number | null` would collapse them at the first
  // `Number("")`.
  coverageTargets: Partial<Record<StaffRole, string>>;
}

function draftOf(template: ShiftTemplate): Draft {
  return {
    id: template.id,
    dayOfWeek: template.day_of_week,
    label: template.label,
    startsAtTime: hhmm(template.starts_at_time),
    endsAtTime: hhmm(template.ends_at_time),
    sortOrder: template.sort_order,
    coverageTargets: Object.fromEntries(
      Object.entries(template.coverage_targets).map(([role, value]) => [role, String(value)]),
    ),
  };
}

function bodyOf(draft: Draft): ShiftTemplateInput {
  return {
    day_of_week: draft.dayOfWeek,
    label: draft.label.trim(),
    starts_at_time: hhmmss(draft.startsAtTime),
    ends_at_time: hhmmss(draft.endsAtTime),
    sort_order: draft.sortOrder,
    // Sparse: a BLANK omits the key («no target»), `"0"` writes `0`
    // («deliberately nobody»). D10's two meanings survive the round trip only
    // because this filter tests the string and never its truthiness.
    coverage_targets: Object.fromEntries(
      Object.entries(draft.coverageTargets)
        .filter(([, value]) => value.trim() !== "")
        .map(([role, value]) => [role, Number(value)]),
    ),
  };
}

// D4's predicate, and it is the SAME one the server applies: `label` and
// `sort_order` are absent, so renaming a shift opens no confirm and deletes
// nothing.
function isMaterialEdit(before: ShiftTemplate, draft: Draft): boolean {
  return (
    before.day_of_week !== draft.dayOfWeek ||
    hhmm(before.starts_at_time) !== draft.startsAtTime ||
    hhmm(before.ends_at_time) !== draft.endsAtTime
  );
}

export interface ShiftTemplatesPaneProps {
  /**
   * ⚠ THIS PANE OWNS THE TEMPLATES READ FOR THE WHOLE SECTION, and the container
   * OBSERVES it rather than repeating it. §1.1's first-run collapse keys on the
   * resolved list, and a second `listShiftTemplates()` in the container both
   * doubled the request on every elevated mount and never learned about the seed
   * — so §1.1's `if` stayed collapsed until a page reload, which is exactly what
   * §5.2 says must not happen («the other three panes mount for the first time»).
   *
   * Called on every resolved list: first load, seed, and every write's refetch.
   */
  onTemplates: (templates: ShiftTemplate[]) => void;
}

export function ShiftTemplatesPane({ onTemplates }: ShiftTemplatesPaneProps) {
  const { t } = useTranslation();
  const [templates, setTemplates] = useState<ShiftTemplate[] | null>(null);
  const [loadFailed, setLoadFailed] = useState(false);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [draftError, setDraftError] = useState<string | null>(null);
  const [writeError, setWriteError] = useState<string | null>(null);
  const [confirmEdit, setConfirmEdit] = useState<Draft | null>(null);
  const [confirmRemove, setConfirmRemove] = useState<ShiftTemplate | null>(null);
  const [seedDone, setSeedDone] = useState<number | null>(null);
  const [invalidated, setInvalidated] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const seedDoneLine = useRef<HTMLParagraphElement>(null);
  // Keyed by weekday, so the remove confirm can land focus on the nearest
  // surviving control in the same group.
  const addButtons = useRef<Record<number, HTMLButtonElement | null>>({});
  const [focusDay, setFocusDay] = useState<number | null>(null);

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

  // One report per resolved list, from the one component that reads it. A load
  // FAILURE reports nothing — the container must not collapse to first-run on a
  // 500, and this pane is already rendering the alert and the retry for it.
  useEffect(() => {
    if (templates !== null) {
      onTemplates(templates);
    }
  }, [templates, onTemplates]);

  // ⚠ SEED SUCCESS UNMOUNTS THE BUTTON SHE JUST PRESSED — the `EmptyState`
  // holding it is replaced by seven populated weekday groups, and the container
  // simultaneously releases three more Cards. Focus falls to <body> under the
  // largest re-render in the feature, so it lands on the line that says how many
  // were created, with the new list after it in tab order
  // (`BookingDetail`'s shipped rescue).
  useEffect(() => {
    if (seedDone !== null) {
      seedDoneLine.current?.focus();
    }
  }, [seedDone]);

  // ⚠ AND THE REMOVE CONFIRM RETURNS FOCUS TO THE ROW IT JUST DELETED. `Modal`
  // returns focus to its trigger on close, but that trigger is the `[הסרה]`
  // button on a row that no longer exists — so on the SUCCESS path only, focus
  // moves to that weekday's add button. On cancel the trigger is still there and
  // the shipped behaviour is right, which is why this overrides nothing else.
  useEffect(() => {
    if (focusDay !== null) {
      addButtons.current[focusDay]?.focus();
      setFocusDay(null);
    }
  }, [focusDay]);

  const mapError = (error: unknown): string => {
    const code = error instanceof ApiError ? error.code : null;
    const key = code === null ? undefined : MAPPED_CODES[code];
    return key === undefined
      ? errorMessage(error)
      : t(key, { total: MAX_TEMPLATES_PER_DAY });
  };

  const seed = async () => {
    setBusy(true);
    setWriteError(null);
    try {
      const result = await api.seedShiftTemplates();
      setTemplates(result.templates);
      setSeedDone(result.created);
    } catch (error) {
      setWriteError(mapError(error));
      // Two managers seeding at once is the only way to reach
      // TEMPLATES_ALREADY_SEEDED, and the winner's templates should appear
      // rather than an error over a blank list.
      if (error instanceof ApiError && error.code === "TEMPLATES_ALREADY_SEEDED") {
        await load();
      }
    } finally {
      setBusy(false);
    }
  };

  const saveDraft = async (current: Draft) => {
    const message = validateShiftTemplate(current.label, current.startsAtTime, current.endsAtTime);
    if (message !== null) {
      setDraftError(message);
      return;
    }
    setDraftError(null);
    setBusy(true);
    setWriteError(null);
    try {
      if (current.id === null) {
        await api.createShiftTemplate(bodyOf(current));
        setInvalidated(null);
      } else {
        const result = await api.updateShiftTemplate(current.id, bodyOf(current));
        setInvalidated(result.invalidated_submissions);
      }
      setDraft(null);
      setConfirmEdit(null);
      await load();
    } catch (error) {
      setWriteError(mapError(error));
    } finally {
      setBusy(false);
    }
  };

  const submitDraft = () => {
    if (draft === null) {
      return;
    }
    const before = templates?.find((row) => row.id === draft.id);
    const count = before?.future_submission_count ?? 0;
    // The confirm opens EXACTLY when the edit is material AND there is something
    // to lose. A label-only edit saves straight through — renaming «משמרת בוקר»
    // to «בוקר» changes nothing anybody answered — and «will delete 0 answers»
    // is noise on the overwhelmingly common case.
    if (before !== undefined && isMaterialEdit(before, draft) && count > 0) {
      setConfirmEdit(draft);
      return;
    }
    void saveDraft(draft);
  };

  const remove = async (template: ShiftTemplate) => {
    setBusy(true);
    setWriteError(null);
    try {
      const result = await api.deleteShiftTemplate(template.id);
      setInvalidated(result.invalidated_submissions);
      setConfirmRemove(null);
      setFocusDay(template.day_of_week);
      await load();
    } catch (error) {
      setWriteError(mapError(error));
      setConfirmRemove(null);
    } finally {
      setBusy(false);
    }
  };

  if (templates === null) {
    return (
      <Card>
        <h2 className="text-xl font-semibold text-ink">{t("shifts.templatesHeading")}</h2>
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
          <Skeleton variant="text" lines={6} />
        )}
      </Card>
    );
  }

  return (
    <Card>
      <h2 className="text-xl font-semibold text-ink">{t("shifts.templatesHeading")}</h2>

      {seedDone !== null && (
        <p role="status" ref={seedDoneLine} tabIndex={-1} className="mt-3 text-base text-ink">
          {t("shifts.seedDone", { total: seedDone })}
        </p>
      )}
      {invalidated !== null && invalidated > 0 && (
        <p role="status" className="mt-3 text-base text-ink">
          {t("shifts.invalidateDone", { total: invalidated })}
        </p>
      )}
      {writeError !== null && (
        <p role="alert" className="mt-3 text-base text-danger">
          {writeError}
        </p>
      )}

      {templates.length === 0 ? (
        <EmptyState
          title={t("shifts.templatesHeading")}
          body={t("shifts.templatesEmptyBody")}
          action={
            // ⚠ RENDERED UNCONDITIONALLY, never gated on a pre-check for opening
            // hours. A pre-check needs a `GET /manage/availability` on every
            // mount purely to hide a control the server already guards with
            // `409 NO_OPENING_HOURS` — a second reader that can disagree with the
            // writer. She learns the same fact one request later, from the only
            // component that actually knows.
            <Button size="md" loading={busy} onClick={() => void seed()}>
              {t("shifts.seed")}
            </Button>
          }
        />
      ) : (
        <div className="mt-4 flex flex-col">
          {DAY_NAMES.map((dayName, day) => {
            const rows = templates.filter((row) => row.day_of_week === day);
            const atCap = rows.length >= MAX_TEMPLATES_PER_DAY;
            return (
              <section key={day} className="flex flex-col gap-3 border-t border-border py-4">
                <h3 className="text-base font-semibold text-ink">{dayName}</h3>
                <ul className="flex flex-col gap-2">
                  {rows.map((row) => (
                    <li key={row.id} className="flex flex-wrap items-center gap-2">
                      <span className="text-base text-ink">{row.label}</span>
                      <bdi dir="ltr" className="text-base text-ink-muted">
                        {hhmm(row.starts_at_time)}–{hhmm(row.ends_at_time)}
                      </bdi>
                      <Button
                        variant="secondary"
                        size="md"
                        onClick={() => {
                          setDraft(draftOf(row));
                          setDraftError(null);
                        }}
                      >
                        {t("shifts.edit")}
                      </Button>
                      <Button
                        variant="danger"
                        size="md"
                        onClick={() => {
                          setConfirmRemove(row);
                        }}
                      >
                        {t("shifts.remove")}
                      </Button>
                    </li>
                  ))}
                </ul>
                <div className="flex flex-wrap items-center gap-2">
                  <Button
                    variant="secondary"
                    size="md"
                    disabled={atCap}
                    ref={(node) => {
                      addButtons.current[day] = node;
                    }}
                    onClick={() => {
                      setDraft({
                        id: null,
                        dayOfWeek: day,
                        label: "",
                        startsAtTime: "09:00",
                        endsAtTime: "14:00",
                        sortOrder: rows.length,
                        // A NEW shift starts with no targets at all, which is
                        // D10's «no target» and renders as a plain count.
                        coverageTargets: {},
                      });
                      setDraftError(null);
                    }}
                  >
                    {t("shifts.addTemplate")}
                  </Button>
                  {/* ⚠ THE REASON IS TEXT, NOT A `title`. A disabled control
                      whose reason lives only in a tooltip is unreachable by
                      keyboard and by AT. One string, two arrivals — this and the
                      `400 TEMPLATE_LIMIT_REACHED` message. */}
                  {atCap && (
                    <span className="text-sm text-ink-muted">
                      {t("shifts.dayLimitReached", { total: MAX_TEMPLATES_PER_DAY })}
                    </span>
                  )}
                </div>
              </section>
            );
          })}
        </div>
      )}

      {draft !== null && (
        <div className="mt-4 flex flex-col gap-3 border-t border-border pt-4">
          <Select
            label={t("shifts.templateDay")}
            value={String(draft.dayOfWeek)}
            onChange={(event) => {
              setDraft({ ...draft, dayOfWeek: Number(event.target.value) });
            }}
          >
            {DAY_NAMES.map((name, index) => (
              <option key={name} value={index}>
                {name}
              </option>
            ))}
          </Select>
          <Input
            label={t("shifts.templateLabel")}
            value={draft.label}
            maxLength={60}
            onChange={(event) => {
              setDraft({ ...draft, label: event.target.value });
            }}
          />
          <TimeField
            label={t("shifts.templateStart")}
            value={draft.startsAtTime}
            onChange={(event) => {
              setDraft({ ...draft, startsAtTime: event.target.value });
            }}
          />
          <TimeField
            label={t("shifts.templateEnd")}
            value={draft.endsAtTime}
            onChange={(event) => {
              setDraft({ ...draft, endsAtTime: event.target.value });
            }}
          />
          {draftError !== null && (
            <p role="alert" className="text-base text-danger">
              {draftError}
            </p>
          )}
          <div className="flex flex-wrap gap-2">
            <Button size="md" loading={busy} onClick={submitDraft}>
              {t("shifts.templateSave")}
            </Button>
            <Button
              variant="secondary"
              size="md"
              onClick={() => {
                setDraft(null);
                setDraftError(null);
              }}
            >
              {t("shifts.templateCancel")}
            </Button>
          </div>
        </div>
      )}

      <Modal
        open={confirmEdit !== null}
        onClose={() => {
          setConfirmEdit(null);
        }}
        title={t("shifts.editTitle")}
        footer={
          <Button
            variant="danger"
            size="md"
            loading={busy}
            onClick={() => {
              if (confirmEdit !== null) {
                void saveDraft(confirmEdit);
              }
            }}
          >
            {t("shifts.templateSave")}
          </Button>
        }
      >
        <p className="text-base text-ink">
          {t("shifts.invalidateWarning", {
            total:
              templates.find((row) => row.id === confirmEdit?.id)?.future_submission_count ?? 0,
          })}
        </p>
      </Modal>

      <Modal
        open={confirmRemove !== null}
        onClose={() => {
          setConfirmRemove(null);
        }}
        title={t("shifts.removeTitle")}
        footer={
          <Button
            variant="danger"
            size="md"
            loading={busy}
            onClick={() => {
              if (confirmRemove !== null) {
                void remove(confirmRemove);
              }
            }}
          >
            {t("shifts.remove")}
          </Button>
        }
      >
        <p className="text-base text-ink">{t("shifts.removeBody")}</p>
        {(confirmRemove?.future_submission_count ?? 0) > 0 && (
          <p className="mt-2 text-base text-ink">
            {t("shifts.invalidateWarning", {
              total: confirmRemove?.future_submission_count ?? 0,
            })}
          </p>
        )}
      </Modal>
    </Card>
  );
}
