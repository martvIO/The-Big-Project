import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Button, Modal, Select } from "@boutique/ui";
import type { RoomAssignment, StaffCard } from "../api";
import { isolateBidi } from "../lib/booking";

// F36. Give the room to a colleague — ELEVATED ONLY, because a handover TAKES a
// room from one worker and gives it to another who has not consented, so "any
// staffer may act on herself" does not reach it (spec D8). Its trigger does not
// exist for the three floor roles, so this dialog is elevated-only by
// construction rather than by a check inside it.
//
// The colleague list is built from the `staff` array THE POLL ALREADY CARRIES:
// no new endpoint and no second fetch, filtered to `id !== staff_user_id` and
// excluding cards whose status is "occupied", so the 409 STAFF_OCCUPIED is
// usually PREVENTED rather than explained.

interface RoomHandoverDialogProps {
  open: boolean;
  assignment: RoomAssignment;
  staff: readonly StaffCard[];
  onClose: () => void;
  onConfirm: (staffId: string, displayName: string) => void;
  /** The residual 409, rendered INSIDE — the dialog stays so she can pick again. */
  error: { text: string; value: string | null } | null;
  busy: boolean;
}

export function RoomHandoverDialog({
  open,
  assignment,
  staff,
  onClose,
  onConfirm,
  error,
  busy,
}: RoomHandoverDialogProps) {
  const { t } = useTranslation();
  const [target, setTarget] = useState("");

  useEffect(() => {
    if (open) {
      setTarget("");
    }
  }, [open]);

  const candidates = staff.filter(
    (member) => member.id !== assignment.staff_user_id && member.status !== "occupied",
  );
  const chosen = candidates.find((member) => member.id === target) ?? candidates[0];

  return (
    <Modal
      open={open}
      // No interpolation: the room is not in doubt, she opened the dialog from
      // its tile.
      title={t("rooms.handoverTitle")}
      onClose={onClose}
      footer={
        <>
          <Button variant="ghost" size="md" fullWidthMobile={false} onClick={onClose}>
            {t("rooms.cancel")}
          </Button>
          {chosen !== undefined && (
            // `secondary` and never `danger`: a handover destroys nothing — the
            // assignment survives, created_at does not move, and every dress
            // binding survives by not being touched (spec D8).
            <Button
              variant="secondary"
              size="md"
              fullWidthMobile={false}
              loading={busy}
              onClick={() => onConfirm(chosen.id, chosen.display_name)}
            >
              {t("rooms.handoverConfirm")}
            </Button>
          )}
        </>
      }
    >
      <div className="space-y-4">
        {chosen === undefined ? (
          // The dialog still opens: a trigger that does nothing is worse than a
          // dialog that explains.
          <p className="text-sm text-ink-muted">{t("rooms.handoverNobody")}</p>
        ) : (
          <Select
            label={t("rooms.handoverPick")}
            className="min-h-11"
            value={chosen.id}
            onChange={(event) => setTarget(event.target.value)}
          >
            {candidates.map((member) => (
              // A colleague on a break is NOT excluded and her option says so:
              // the server accepts the handover and the indexes do not forbid
              // it, so hiding her would be the client asserting a rule the
              // server does not have. An <option> takes no markup, so the name
              // needs no <bdi> — the same exemption an aria-label gets.
              <option key={member.id} value={member.id}>
                {member.break_started_at === null
                  ? member.display_name
                  : t("rooms.handoverOnBreak", { name: member.display_name })}
              </option>
            ))}
          </Select>
        )}
        {error !== null && (
          // The NOTICE register, never danger: the receiving colleague took a
          // room between the tick and the confirm, which is the ordinary shop
          // floor and nobody's mistake.
          <p role="alert" className="text-sm font-semibold text-warning-text">
            {error.value === null ? error.text : isolateBidi(error.text, error.value)}
          </p>
        )}
      </div>
    </Modal>
  );
}
