import { useEffect, useId, useState } from "react";
import { Trans, useTranslation } from "react-i18next";
import { Button, Modal } from "@boutique/ui";
import type { AvailabilityState, RosterAssignment, RosterStaffRef, ShiftTemplate } from "../api";
import { roleLabelKey } from "../lib/roles";

// The shift's EDITOR, not an "add" picker (design §3). It opens on «הוספה
// למשמרת», states who is already on the shift, and offers everyone else — one
// control per person, and the control flips «הוספה» ⇄ «הסרה» in place.
//
// ⚠ THE FLIP IS THE ONE STRUCTURAL DECISION HERE. A dialog that removed the row
// it had just assigned would drop focus to `<body>` on the most repeated act in
// the feature, twelve times a session, and would need F39's `ref` +
// `tabIndex={-1}` rescue every time. The control surviving its own press is the
// house default and the reason there is nothing to rescue.
//
// ⚠ NO `primary` ANYWHERE IN THIS DIALOG. `Button`'s variant defaults to
// `primary` and `primary` is gold — an unannotated button here is a gold button
// on every row (design §2.0). The dialog is an editor; `secondary` for add and
// for the override confirm, `danger` for remove.

const hhmm = (time: string) => time.slice(0, 5);

// The bucket order IS the design (§3.2): assigned first, then the answers most
// likely to be taken up, then the refusal. Stable inside each bucket in the
// SERVER's `staff[]` order, so the list does not reshuffle from shift to shift.
const BUCKET: Record<string, number> = {
  preferred: 0,
  available: 1,
  unanswered: 2,
  unavailable: 3,
};

// ⚠ «לא נרשם», NOT «טרם הגישה». `shifts.notSubmitted` is a fact about the
// PERSON — she has not submitted at all — and it is `WeekSubmissionsPane`'s
// badge. Here the fact is about THIS SHIFT: a staffer who answered eleven of
// twelve and left this one blank has emphatically «הגישה».
const STATE_KEY: Record<AvailabilityState, string> = {
  preferred: "shifts.states.preferred",
  available: "shifts.states.available",
  unavailable: "shifts.states.unavailable",
};

export interface RosterCellDialogProps {
  open: boolean;
  onClose: () => void;
  /** The weekday word, for the body's first line. */
  dayName: string;
  template: ShiftTemplate;
  assignments: RosterAssignment[];
  /** Live staffers in the server's order, each with her state per template. */
  staff: RosterStaffRef[];
  /** staff_user_id → how many shifts she holds across the WHOLE week (§3.3). */
  weekCounts: Record<string, number>;
  /** The pane's one write-failure sentence, rendered here while this is open. */
  error: string | null;
  onAssign: (staffUserId: string, acknowledgeOverride: boolean) => Promise<boolean>;
  onRemove: (assignmentId: string) => Promise<boolean>;
}

export function RosterCellDialog({
  open,
  onClose,
  dayName,
  template,
  assignments,
  staff,
  weekCounts,
  error,
  onAssign,
  onRemove,
}: RosterCellDialogProps) {
  const { t } = useTranslation();
  const identityId = useId();
  // ⚠ AT MOST ONE ROW ARMED (§3.4). Two armed rows is two half-committed
  // overrides on one screen with no way to tell at a glance which «הוספה» is
  // still a first tap.
  const [armed, setArmed] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [cue, setCue] = useState<{ key: string; name: string } | null>(null);

  useEffect(() => {
    if (!open) {
      setArmed(null);
      setCue(null);
    }
  }, [open]);

  const assignedBy = new Map(assignments.map((row) => [row.staff_user_id, row]));

  const rows = staff
    .map((person, index) => {
      const assignment = assignedBy.get(person.id) ?? null;
      const state = person.states[template.id] ?? null;
      return { person, assignment, state, index };
    })
    .sort((a, b) => {
      const bucketA = a.assignment === null ? BUCKET[a.state ?? "unanswered"] + 1 : 0;
      const bucketB = b.assignment === null ? BUCKET[b.state ?? "unanswered"] + 1 : 0;
      return bucketA === bucketB ? a.index - b.index : bucketA - bucketB;
    });

  const unassigned = rows.filter((row) => row.assignment === null);
  // §3.4: told BEFORE she reads eight names and taps one, not after.
  const allUnavailable =
    unassigned.length > 0 && unassigned.every((row) => row.state === "unavailable");

  const write = async (
    key: string,
    cueKey: string,
    name: string,
    run: () => Promise<boolean>,
  ) => {
    setBusy(key);
    setCue(null);
    try {
      // ⚠ RE-ARMED IN `.finally()`, NEVER IN THE SUCCESS BRANCH, so a failed
      // write leaves a live button rather than a permanently spinning one.
      if (await run()) {
        setArmed(null);
        setCue({ key: cueKey, name });
      }
    } finally {
      setBusy(null);
    }
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={t("shifts.cellDialogTitle")}
      describedById={identityId}
    >
      {/* ⚠ `ModalProps.title` IS A `string`, so it cannot carry a
          `<bdi dir="ltr">` time range. The shift's identity is the body's first
          line instead, composed in JSX and wired through `describedById` so the
          dialog announces WHICH shift on open. */}
      <p id={identityId} className="text-base text-ink">
        {dayName} · {template.label} ·{" "}
        <bdi dir="ltr">
          {hhmm(template.starts_at_time)}–{hhmm(template.ends_at_time)}
        </bdi>
      </p>

      {/* The dialog's TOP region: assign and remove only. The override warning
          lives in its own row (§3.1) and the two can never fire together —
          arming writes nothing, and any write clears the arm. */}
      <p role="status" className="mt-2 text-sm text-ink-muted">
        {cue !== null && (
          <Trans i18nKey={cue.key} values={{ name: cue.name }} components={{ bdi: <bdi /> }} />
        )}
      </p>

      {error !== null && (
        <p role="alert" className="mt-2 text-base text-danger">
          {error}
        </p>
      )}

      {allUnavailable && (
        <p className="mt-2 text-base text-ink">{t("shifts.cellAllUnavailable")}</p>
      )}

      <ul className="mt-3 flex flex-col gap-2">
        {rows.map(({ person, assignment, state }) => {
          const roleKey = roleLabelKey(person.role);
          const isArmed = armed === person.id;
          const overrides = assignment === null && state === "unavailable";
          const key = assignment === null ? `add:${person.id}` : `remove:${assignment.id}`;
          return (
            <li
              key={person.id}
              className="flex flex-col gap-1 border-t border-border pt-2 first:border-t-0 first:pt-0"
            >
              <div className="flex flex-wrap items-center gap-2">
                {/* A BARE `<bdi>` with `break-words` — a `dir="ltr"` on a Hebrew
                    name is itself a defect, and a display name never truncates. */}
                <bdi className="break-words text-base text-ink">{person.display_name}</bdi>
                <span className="text-sm text-ink-muted">
                  {assignment !== null
                    ? t("shifts.cellAssigned")
                    : state === null
                      ? t("shifts.stateUnanswered")
                      : t(STATE_KEY[state])}
                </span>
                {roleKey !== null && (
                  <span className="text-sm text-ink-muted">{t(roleKey)}</span>
                )}
                <span className="text-sm text-ink-muted">
                  {t("shifts.cellWeekCount", { total: weekCounts[person.id] ?? 0 })}
                </span>
                {assignment === null ? (
                  <Button
                    variant="secondary"
                    size="md"
                    loading={busy === key}
                    aria-label={
                      isArmed ? undefined : t("shifts.cellAddAria", { name: person.display_name })
                    }
                    onClick={() => {
                      // ⚠ THE FIRST TAP ON AN «לא זמינה» ROW WRITES NOTHING
                      // (D11). The override is always a second, deliberate act.
                      if (overrides && !isArmed) {
                        setCue(null);
                        setArmed(person.id);
                        return;
                      }
                      void write(key, "shifts.cellAssignedCue", person.display_name, () =>
                        onAssign(person.id, isArmed),
                      );
                    }}
                  >
                    {isArmed ? t("shifts.assignAnyway") : t("shifts.cellAdd")}
                  </Button>
                ) : (
                  <Button
                    variant="danger"
                    size="md"
                    loading={busy === key}
                    aria-label={t("shifts.cellRemoveAria", { name: person.display_name })}
                    onClick={() => {
                      void write(key, "shifts.cellRemovedCue", person.display_name, () =>
                        onRemove(assignment.id),
                      );
                    }}
                  >
                    {t("shifts.cellRemove")}
                  </Button>
                )}
              </div>
              {isArmed && (
                // ⚠ IN THE ROW, never in the top region. In a 448px modal on a
                // 375px phone, a warning painted above her scroll position while
                // the button that just changed is under her finger is a label
                // change with no visible reason — and the second tap is the
                // write. The warning must be adjacent to the button whose
                // meaning it changed.
                <p role="status" className="text-sm text-ink">
                  <Trans
                    i18nKey="shifts.overrideWarning"
                    values={{ name: person.display_name }}
                    components={{ bdi: <bdi /> }}
                  />
                </p>
              )}
            </li>
          );
        })}
      </ul>
    </Modal>
  );
}
