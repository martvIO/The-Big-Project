import { useCallback, useEffect, useRef, useState } from "react";
import { Trans, useTranslation } from "react-i18next";
import { Badge, Button, Card, Checkbox, Skeleton, formatDateRange } from "@boutique/ui";
import { api, ApiError, errorMessage } from "../api";
import type { RosterShift, RosterWeek, StaffRole } from "../api";
import { RangeText } from "../lib/dateRange";
import { jerusalemDate, jerusalemTime, plainDayMonth } from "../lib/jerusalem";
import { ROLE_OPTIONS, roleLabelKey } from "../lib/roles";
import { DAYS_IN_WEEK, DAY_NAMES, FIRST_OFFSET, LAST_OFFSET, addDays } from "../lib/week";
import { RosterCellDialog } from "./RosterCellDialog";

// The roster builder — elevated, the fifth Card in `ShiftsSection` (design §2).
//
// ⚠ THE ONE SENTENCE THAT GOVERNS THIS PANE: the owner's failure is «I published
// and missed one», not «this took too long». Everything below is arranged so the
// count of under-staffed shifts is in her eye BEFORE the publish button — the
// DOM order `count → publish → filter` is §2.7's entire substitute for a publish
// confirmation, and reordering it ships the feature with neither.
//
// ⚠ EXACTLY ONE `primary` ON THIS PANE — publish. `Button`'s variant defaults to
// `primary` and `primary` is gold, so an unannotated control here is one of
// twelve gold «הוספה למשמרת» buttons against the gold law's whole point (§2.0).

const MAPPED_CODES: Record<string, string> = {
  AVAILABILITY_CONFLICT: "shifts.errors.availabilityConflict",
  NOT_SHIFT_MANAGER_ELIGIBLE: "shifts.errors.notEligible",
  SHIFT_MANAGER_SLOT_TAKEN: "shifts.errors.managerSlotTaken",
  WEEK_OUT_OF_RANGE: "shifts.errors.weekOutOfRange",
  NOT_AUTHORIZED: "shifts.errors.rosterNotAuthorized",
  NOT_FOUND: "shifts.errors.notFound",
};

// Codes whose whole meaning is «the screen and the server disagree» (§2.9).
const REFETCH_CODES = new Set([
  "NOT_SHIFT_MANAGER_ELIGIBLE",
  "SHIFT_MANAGER_SLOT_TAKEN",
  "WEEK_OUT_OF_RANGE",
  "NOT_FOUND",
]);

const hhmm = (time: string) => time.slice(0, 5);

function byWeekday(shifts: RosterShift[]): [number, RosterShift[]][] {
  const groups = new Map<number, RosterShift[]>();
  for (const shift of shifts) {
    const day = groups.get(shift.template.day_of_week) ?? [];
    day.push(shift);
    groups.set(shift.template.day_of_week, day);
  }
  return [...groups.entries()].sort(([a], [b]) => a - b);
}

// A shift is SHORT iff some role she set a target for is under it. A missing
// shift manager is deliberately not counted (§2.6): a target is an expectation
// the owner stated; a quiet Tuesday with no manager may be entirely intentional,
// and on a fresh boutique NOBODY is eligible at all.
function isShort(shift: RosterShift): boolean {
  return Object.entries(shift.coverage_targets).some(
    ([role, target]) => (shift.assigned_by_role[role as StaffRole] ?? 0) < (target ?? 0),
  );
}

export function RosterPane() {
  const { t } = useTranslation();
  // ⚠ THE REQUESTED WEEK, NOT THE RESOLVED ONE — `undefined` means «the server's
  // default», which is next week. No pane on this console computes a week from
  // the device clock.
  const [requestedWeek, setRequestedWeek] = useState<string | undefined>(undefined);
  const [offset, setOffset] = useState(0);
  const [week, setWeek] = useState<RosterWeek | null>(null);
  const [loadFailed, setLoadFailed] = useState(false);
  const [writeError, setWriteError] = useState<string | null>(null);
  const [publishCue, setPublishCue] = useState(false);
  const [publishing, setPublishing] = useState(false);
  const [busy, setBusy] = useState<string[]>([]);
  // ⚠ THE FILTERED SET IS CAPTURED ON TICK AND DOES NOT RE-EVALUATE (§2.6).
  // Live filtering unmounts the `<section>` under her open dialog on the write
  // that closes a shortage — focus to `<body>`, the dialog's return target gone,
  // and the list reflowing on every single assignment.
  const [heldShort, setHeldShort] = useState<string[] | null>(null);
  // ⚠ TWO PIECES OF STATE, NOT ONE, AND `Modal` STAYS MOUNTED THROUGH THE CLOSE.
  // `packages/ui`'s Modal is a native `<dialog>`: the browser returns focus to
  // the trigger when `close()` runs, and unmounting the element instead drops
  // focus to `<body>` on every Esc — which the e2e leg caught. Every shipped
  // call site passes `open={x !== null}` on an always-mounted Modal, and this is
  // that shape with the shift id kept so the body has something to render while
  // it closes.
  const [dialogShiftId, setDialogShiftId] = useState<string | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);

  // F-A, the response-ordering guard. §2.0 permits two concurrent writes on ONE
  // shift by design, so without a per-shift ticket the earlier-issued response
  // arriving second silently drops the later assignment.
  const tickets = useRef(new Map<string, number>());
  // The focus rescue for §10: removing an assignment unmounts its own button, so
  // focus lands on that shift's «הוספה למשמרת» — the nearest surviving control
  // in the same group. `ShiftTemplatesPane`'s shipped `addButtons` shape.
  const addButtons = useRef(new Map<string, HTMLButtonElement | null>());
  // §10's one guard on the shipped return-to-trigger: if that shift's section is
  // gone on close (a template soft-deleted under her), the trigger is gone too,
  // so focus lands on the pane's own heading rather than on `<body>`.
  const headingRef = useRef<HTMLHeadingElement>(null);

  const load = useCallback(async () => {
    setLoadFailed(false);
    try {
      const payload = await api.getRoster(requestedWeek);
      setWeek(payload);
    } catch {
      setWeek(null);
      setLoadFailed(true);
    }
  }, [requestedWeek]);

  useEffect(() => {
    void load();
  }, [load]);

  // §10's guard on `Modal`'s shipped return-to-trigger: the trigger is that
  // shift's «הוספה למשמרת», so if the shift itself has gone (a template
  // soft-deleted under her, or a refetch that dropped it) there is nothing to
  // return to and the browser would leave focus on `<body>`.
  const shiftGone =
    dialogShiftId !== null &&
    week !== null &&
    !week.shifts.some((shift) => shift.template.id === dialogShiftId);
  useEffect(() => {
    if (shiftGone) {
      setDialogShiftId(null);
      setDialogOpen(false);
      headingRef.current?.focus();
    }
  }, [shiftGone]);

  const fail = (error: unknown) => {
    const code = error instanceof ApiError ? error.code : null;
    const key = code === null ? undefined : MAPPED_CODES[code];
    setWriteError(key === undefined ? errorMessage(error) : t(key));
    if (code !== null && REFETCH_CODES.has(code)) {
      void load();
    }
  };

  const applyShift = (templateId: string, ticket: number, shift: RosterShift) => {
    if (tickets.current.get(templateId) !== ticket) {
      return;
    }
    setWeek((current) =>
      current === null
        ? current
        : {
            ...current,
            shifts: current.shifts.map((existing) =>
              existing.template.id === templateId ? shift : existing,
            ),
          },
    );
  };

  const writeShift = async (
    templateId: string,
    key: string,
    run: () => Promise<RosterShift>,
  ): Promise<boolean> => {
    const ticket = (tickets.current.get(templateId) ?? 0) + 1;
    tickets.current.set(templateId, ticket);
    setBusy((current) => [...current, key]);
    setWriteError(null);
    setPublishCue(false);
    try {
      applyShift(templateId, ticket, await run());
      return true;
    } catch (error) {
      fail(error);
      return false;
    } finally {
      // Re-armed here and never in the success branch, so a failed write leaves
      // a live button rather than a permanently spinning one.
      setBusy((current) => current.filter((entry) => entry !== key));
    }
  };

  const step = (weeks: number) => {
    if (week === null) {
      return;
    }
    // Everything transient belongs to the week she is leaving — including the
    // held filter set, which is a cut of THAT week's shortages.
    setDialogOpen(false);
    setDialogShiftId(null);
    setWriteError(null);
    setPublishCue(false);
    setHeldShort(null);
    setOffset((current) => current + weeks);
    setRequestedWeek((current) => addDays(current ?? week.week_start, weeks * DAYS_IN_WEEK));
  };

  const publish = async () => {
    if (week === null) {
      return;
    }
    setPublishing(true);
    setWriteError(null);
    try {
      // Idempotent (D7). A republish that changes nothing writes nothing — and
      // the cue still shows, because telling her «nothing happened» when the
      // outcome she wanted is the outcome that holds would be telling her she
      // was wrong when she was right.
      setWeek(await api.publishRoster(week.week_start));
      setPublishCue(true);
    } catch (error) {
      fail(error);
    } finally {
      setPublishing(false);
    }
  };

  if (week === null) {
    return (
      <Card>
        <h2 ref={headingRef} tabIndex={-1} className="text-xl font-semibold text-ink">
          {t("shifts.rosterHeading")}
        </h2>
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

  const weekCounts: Record<string, number> = {};
  for (const shift of week.shifts) {
    for (const row of shift.assignments) {
      weekCounts[row.staff_user_id] = (weekCounts[row.staff_user_id] ?? 0) + 1;
    }
  }

  // ⚠ THE COUNT LINE AND P1 RENDER UNDER EXACTLY THE SAME CONDITION, and the
  // gate is not optional. `coverage_targets` ships `NOT NULL DEFAULT '{}'`, so
  // on a boutique that has never set one the «is short» predicate is
  // structurally false forever: ungated, she ticks the box and every weekday
  // section disappears with nothing on screen to distinguish that from a load
  // bug. Both are answers about targets, and a boutique with no targets has no
  // question.
  const hasTargets = week.shifts.some(
    (shift) => Object.keys(shift.coverage_targets).length > 0,
  );
  const shortIds = week.shifts.filter(isShort).map((shift) => shift.template.id);
  const noSubmissions = week.staff.every(
    (person) => Object.keys(person.states).length === 0,
  );
  const noneEligible = week.staff.every((person) => !person.shift_manager_eligible);
  const visible =
    heldShort === null
      ? week.shifts
      : week.shifts.filter((shift) => heldShort.includes(shift.template.id));
  const open = week.shifts.find((shift) => shift.template.id === dialogShiftId) ?? null;

  return (
    <Card>
      <h2 ref={headingRef} tabIndex={-1} className="text-xl font-semibold text-ink">
        {t("shifts.rosterHeading")}
      </h2>

      <div className="mt-3 flex flex-wrap items-center gap-2">
        {/* Words, not chevrons (DL20) — and there is no directional glyph to get
            backwards in RTL. `FIRST_OFFSET`/`LAST_OFFSET` verbatim from
            `lib/week.ts`: this pane's window is the shipped one. */}
        <Button
          variant="secondary"
          size="md"
          disabled={offset <= FIRST_OFFSET}
          onClick={() => {
            step(-1);
          }}
        >
          {t("shifts.prevWeek")}
        </Button>
        <Button
          variant="secondary"
          size="md"
          disabled={offset >= LAST_OFFSET}
          onClick={() => {
            step(1);
          }}
        >
          {t("shifts.nextWeek")}
        </Button>
        <p role="status" className="text-base text-ink">
          {t("shifts.weekLabel")}{" "}
          <RangeText range={formatDateRange(week.week_start, week.week_end)} />
        </p>
      </div>

      <p className="mt-2 text-base text-ink">
        {week.published_at === null ? (
          t("shifts.rosterDraft")
        ) : (
          <Trans
            i18nKey="shifts.rosterPublished"
            values={{
              name: week.published_by_name ?? "",
              date: jerusalemDate(week.published_at),
              time: jerusalemTime(week.published_at),
            }}
            components={{ bdi: <bdi /> }}
          />
        )}
      </p>
      {week.edited_since_publish && (
        <p className="mt-1 text-base text-ink">{t("shifts.rosterEditedSincePublish")}</p>
      )}
      {/* The offset is how this pane knows WHICH KIND of week it is showing —
          the origin is the server's default week, never a device clock. Neither
          line blocks anything: D7 is explicit that a running week is not
          special-cased. */}
      {offset === -1 && (
        <p className="mt-1 text-base text-ink">{t("shifts.rosterInProgressWeek")}</p>
      )}
      {offset <= -2 && <p className="mt-1 text-base text-ink">{t("shifts.rosterPastWeek")}</p>}
      {noSubmissions && (
        <p className="mt-1 text-sm text-ink-muted">{t("shifts.noSubmissionsWeek")}</p>
      )}
      {noneEligible && (
        // Once, in the header block — never once per shift. Twelve copies of one
        // sentence is the repetition the floor board's week line also removes.
        <p className="mt-1 text-sm text-ink-muted">{t("shifts.managerNoneEligible")}</p>
      )}

      {/* ⚠ COUNT → PUBLISH → FILTER, AND THE DOM ORDER IS LOAD-BEARING (§2.7).
          Publish above the count is the defect this ordering exists to prevent:
          a keyboard or screen-reader user reaches «פרסום הסידור» without the
          number ever having been read, and a sighted owner on a 375px phone has
          it below the fold. */}
      {hasTargets && (
        <p role="status" className="mt-3 text-base text-ink">
          {shortIds.length === 0
            ? t("shifts.shortageNone")
            : t("shifts.shortageCount", { total: shortIds.length })}
          {heldShort !== null && ` ${t("shifts.shortageFilterOn")}`}
        </p>
      )}

      <div className="mt-2 flex flex-wrap items-center gap-3">
        <Button size="md" loading={publishing} onClick={() => void publish()}>
          {t(week.published_at === null ? "shifts.publish" : "shifts.republish")}
        </Button>
        {publishCue && (
          <span role="status" className="text-sm text-ink-muted">
            {t("shifts.publishDone")}
          </span>
        )}
      </div>

      {hasTargets && (
        <div className="mt-1">
          <Checkbox
            label={t("shifts.shortageFilter")}
            checked={heldShort !== null}
            onCheckedChange={(checked) => {
              setHeldShort(checked ? shortIds : null);
            }}
          />
        </div>
      )}

      {writeError !== null && !dialogOpen && (
        <p role="alert" className="mt-2 text-base text-danger">
          {writeError}
        </p>
      )}

      {byWeekday(visible).map(([day, dayShifts]) => (
        <section key={day} className="mt-5 flex flex-col gap-4">
          {/* ⚠ WEEKDAY IS A HEADING, NOT A CAPTION (P2). `label` is free operator
              text with no uniqueness rule, so six `h3`s all reading «משמרת בוקר
              · 09:00–14:00» is a screen on which the owner rosters the wrong
              day — and heading navigation is the only way through twelve shifts
              without tabbing every control. */}
          <h3 className="text-base font-semibold text-ink">
            {t("shifts.dayHeading", {
              day: DAY_NAMES[day],
              date: plainDayMonth(addDays(week.week_start, day)),
            })}
          </h3>
          {dayShifts.map((shift) => {
            const shiftName = `${DAY_NAMES[day]} · ${shift.template.label}`;
            const manager = shift.assignments.find((row) => row.is_shift_manager) ?? null;
            const eligible = new Set(
              week.staff.filter((person) => person.shift_manager_eligible).map((p) => p.id),
            );
            return (
              <section
                key={shift.template.id}
                className="flex flex-col gap-2 border-t border-border pt-3"
              >
                <h4 className="text-base font-semibold text-ink">
                  {shift.template.label} ·{" "}
                  <bdi dir="ltr">
                    {hhmm(shift.template.starts_at_time)}–{hhmm(shift.template.ends_at_time)}
                  </bdi>
                </h4>

                <p className="text-sm text-ink-muted">
                  {manager === null ? (
                    t("shifts.managerNone")
                  ) : (
                    <Trans
                      i18nKey="shifts.managerLine"
                      values={{ name: manager.display_name }}
                      components={{ bdi: <bdi /> }}
                    />
                  )}
                </p>

                {/* Sparse, in `ROLE_OPTIONS` order so the lines sit identically
                    on all twelve shifts. «חסר איוש» is a WORD, never a colour. */}
                {ROLE_OPTIONS.map((role) => {
                  const target = shift.coverage_targets[role];
                  const assigned = shift.assigned_by_role[role] ?? 0;
                  const roleKey = roleLabelKey(role);
                  if (roleKey === null || (target === undefined && assigned === 0)) {
                    return null;
                  }
                  if (target === undefined) {
                    return (
                      <p key={role} className="text-sm text-ink">
                        {t("shifts.coverageNoTarget", { role: t(roleKey), total: assigned })}
                      </p>
                    );
                  }
                  return (
                    <p key={role} className="flex flex-wrap items-center gap-2 text-sm text-ink">
                      {t("shifts.coverage", { role: t(roleKey), assigned, target })}
                      {assigned < target && (
                        <Badge variant="warning">{t("shifts.coverageShort")}</Badge>
                      )}
                    </p>
                  );
                })}

                {shift.assignments.length === 0 ? (
                  <p className="text-sm text-ink-muted">{t("shifts.emptyShift")}</p>
                ) : (
                  <ul className="flex flex-col gap-2">
                    {shift.assignments.map((row) => {
                      const roleKey = roleLabelKey(row.role);
                      const live = week.staff.find((person) => person.id === row.staff_user_id);
                      const stale =
                        row.override_of_state === null &&
                        live?.states[shift.template.id] === "unavailable";
                      const managerKey = `manager:${row.id}`;
                      const removeKey = `remove:${row.id}`;
                      return (
                        <li key={row.id} className="flex flex-col gap-1">
                          <div className="flex flex-wrap items-center gap-2">
                            <bdi className="break-words text-base text-ink">
                              {row.display_name}
                            </bdi>
                            {roleKey !== null && (
                              <span className="text-sm text-ink-muted">{t(roleKey)}</span>
                            )}
                            {row.override_of_state !== null && (
                              <Badge variant="warning">{t("shifts.overrideBadge")}</Badge>
                            )}
                            {/* Clear-then-set, two deliberate acts (§2.5). One
                                control doing two writes would, on a failure
                                between them, leave the shift with no manager at
                                all and say nothing. */}
                            {(row.is_shift_manager ||
                              (manager === null && eligible.has(row.staff_user_id))) && (
                              <Button
                                variant="secondary"
                                size="md"
                                loading={busy.includes(managerKey)}
                                aria-label={t(
                                  row.is_shift_manager
                                    ? "shifts.clearManagerAria"
                                    : "shifts.setManagerAria",
                                  { name: row.display_name },
                                )}
                                onClick={() => {
                                  void writeShift(shift.template.id, managerKey, () =>
                                    api.assignToShift({
                                      week_start: week.week_start,
                                      shift_template_id: shift.template.id,
                                      staff_user_id: row.staff_user_id,
                                      is_shift_manager: !row.is_shift_manager,
                                      acknowledge_override: false,
                                    }),
                                  );
                                }}
                              >
                                {t(
                                  row.is_shift_manager
                                    ? "shifts.clearManager"
                                    : "shifts.setManager",
                                )}
                              </Button>
                            )}
                            {/* ⚠ THE ACCESSIBLE NAME CARRIES THE SHIFT AS WELL AS
                                THE PERSON. Dana is on four shifts, so a rotor
                                listing the pane's buttons would otherwise show
                                four identically-named controls. */}
                            <Button
                              variant="danger"
                              size="md"
                              loading={busy.includes(removeKey)}
                              aria-label={t("shifts.removeAssignmentAria", {
                                name: row.display_name,
                                shift: shiftName,
                              })}
                              onClick={() => {
                                void writeShift(shift.template.id, removeKey, () =>
                                  api.removeAssignment(row.id),
                                ).then(() => {
                                  addButtons.current.get(shift.template.id)?.focus();
                                });
                              }}
                            >
                              {t("shifts.removeAssignment")}
                            </Button>
                          </div>
                          {stale && (
                            <p className="text-sm text-ink-muted">
                              <Trans
                                i18nKey="shifts.unavailableAfterAssign"
                                values={{ name: row.display_name }}
                                components={{ bdi: <bdi /> }}
                              />
                            </p>
                          )}
                        </li>
                      );
                    })}
                  </ul>
                )}

                <div>
                  <Button
                    variant="secondary"
                    size="md"
                    ref={(node) => {
                      addButtons.current.set(shift.template.id, node);
                    }}
                    aria-label={t("shifts.addToShiftAria", { shift: shiftName })}
                    onClick={() => {
                      setWriteError(null);
                      setPublishCue(false);
                      setDialogShiftId(shift.template.id);
                      setDialogOpen(true);
                    }}
                  >
                    {t("shifts.addToShift")}
                  </Button>
                </div>
              </section>
            );
          })}
        </section>
      ))}

      {open !== null && (
        <RosterCellDialog
          open={dialogOpen}
          onClose={() => {
            setDialogOpen(false);
          }}
          dayName={DAY_NAMES[open.template.day_of_week]}
          template={open.template}
          assignments={open.assignments}
          staff={week.staff}
          weekCounts={weekCounts}
          error={writeError}
          onAssign={(staffUserId, acknowledgeOverride) =>
            writeShift(open.template.id, `add:${staffUserId}`, () =>
              api.assignToShift({
                week_start: week.week_start,
                shift_template_id: open.template.id,
                staff_user_id: staffUserId,
                is_shift_manager: false,
                acknowledge_override: acknowledgeOverride,
              }),
            )
          }
          onRemove={(assignmentId) =>
            writeShift(open.template.id, `remove:${assignmentId}`, () =>
              api.removeAssignment(assignmentId),
            )
          }
        />
      )}
    </Card>
  );
}
