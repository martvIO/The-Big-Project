import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Button, Input, Modal, Select } from "@boutique/ui";
import type { StaffCard } from "../api";
import { isolateBidi } from "../lib/booking";
import { useSos } from "../lib/sos-context";
import { MAX_SOS_NOTE_LENGTH } from "../validation";

/**
 * F37. One dialog, two triggers — a room tile and the SOS centre — whose open
 * state `FloorPanel` owns, because it is the common parent of both.
 *
 * ⚠ TWO OF ITS FOUR OUTCOMES KEEP IT OPEN, and both are focus moves the spec did
 * not name (deck F-7). `Button` is `disabled={disabled || loading}`, so a real
 * browser blurs the send control the instant the request starts; a <dialog>
 * whose focused child is then REPLACED drops focus to the dialog element or to
 * <body> depending on engine. MOVE E and MOVE F are what stop the one message
 * the ruling mandates, and the one instruction that matters on a bad connection,
 * from being unreachable by keyboard.
 */

interface SosRaiseDialogProps {
  open: boolean;
  /** `FloorPanel`'s staff list — the panel already holds it, so this is a prop. */
  staff: readonly StaffCard[];
  selfId: string;
  /** The tile she is standing in, or `null` from the SOS centre. */
  assignmentId: string | null;
  onCue: (cue: { text: string; name: string | null }) => void;
  onClose: () => void;
}

export function SosRaiseDialog({
  open,
  staff,
  selfId,
  assignmentId,
  onCue,
  onClose,
}: SosRaiseDialogProps) {
  const { t } = useTranslation();
  const { raise } = useSos();

  const [target, setTarget] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [rerouted, setRerouted] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);

  const ackRef = useRef<HTMLButtonElement>(null);
  const sendRef = useRef<HTMLButtonElement>(null);
  const alertRef = useRef<HTMLParagraphElement>(null);

  useEffect(() => {
    // Every open starts clean — a note typed and cancelled must not come back on
    // the next emergency, and neither must a rerouted body.
    if (open) {
      setTarget("");
      setNote("");
      setRerouted(null);
      setFailed(false);
    }
  }, [open]);

  useEffect(() => {
    // MOVE E — «הבנתי» REPLACES the send control, so the element that had focus
    // has just unmounted. Unconditional, deliberately: this transition only ever
    // happens as the direct result of her own tap, and the alternative is focus
    // sitting on the <dialog> (or on <body> inside it) with the one message the
    // ruling mandates unreachable by keyboard.
    if (rerouted !== null) {
      ackRef.current?.focus();
    }
  }, [rerouted]);

  useEffect(() => {
    // MOVE F — the failure alert appears where the send control's blur left
    // focus, and WHERE THAT IS DIFFERS BY ENGINE: a real browser disables the
    // button and drops focus to the <dialog> or to <body>; jsdom does not blur a
    // disabled element and leaves it on the button. All three are «she tapped
    // send and has not moved on», which is the actual condition — and none of
    // them is the note field, so a 5xx landing after she has tabbed back to it
    // still does not yank her out.
    if (!failed) {
      return;
    }
    const active = document.activeElement;
    if (active === document.body || active?.tagName === "DIALOG" || active === sendRef.current) {
      alertRef.current?.focus();
    }
  }, [failed]);

  const send = async () => {
    setBusy(true);
    setFailed(false);
    const outcome = await raise({
      target_staff_user_id: target === "" ? null : target,
      fitting_room_assignment_id: assignmentId,
      note: note.trim() === "" ? null : note.trim(),
    });
    setBusy(false);
    if (outcome.failure !== null || outcome.raised === null) {
      // ⚠ NEVER `FALLBACK_ERROR_MESSAGE`. «נסי שוב» alone is the wrong
      // instruction on the one screen in the product where «open the curtain and
      // shout» is the right one — and a retry costs one tap because the note
      // survives. A duplicate is noise, not corruption.
      setFailed(true);
      return;
    }
    if (outcome.raised.rerouted) {
      setRerouted(outcome.raised.alert.target_name ?? targetName());
      return;
    }
    onCue({ text: t("sos.raisedCue"), name: null });
    onClose();
  };

  const targetName = (): string => {
    const chosen = staff.find((one) => one.id === target);
    return chosen?.display_name ?? t("sos.targetManager");
  };

  const body =
    rerouted === null ? (
      <div className="space-y-4">
        <Select
          label={t("sos.targetPick")}
          className="min-h-11"
          value={target}
          onChange={(event) => setTarget(event.target.value)}
        >
          {/* FIRST and DEFAULT: `value=""` is the shift-manager ROLE, the one
              route whose audience can never be empty. */}
          <option value="">{t("sos.targetManager")}</option>
          {staff
            // ⚠ HERSELF EXCLUDED. The server refuses a self-target with a 400,
            // and excluding it PREVENTS the error rather than explaining it.
            .filter((one) => one.id !== selfId)
            .map((one) => (
              <option key={one.id} value={one.id}>
                {/* A colleague on a break is ANNOTATED, never excluded — a
                    seamstress on a five-minute break is exactly who you want
                    for a corset back. The shipped string, reused whole. */}
                {one.break_started_at === null
                  ? one.display_name
                  : t("rooms.handoverOnBreak", { name: one.display_name })}
              </option>
            ))}
        </Select>
        <Input
          label={t("sos.notePick")}
          help={t("sos.noteOptional")}
          className="min-h-11"
          maxLength={MAX_SOS_NOTE_LENGTH}
          value={note}
          onChange={(event) => setNote(event.target.value)}
        />
        {failed && (
          <p
            ref={alertRef}
            role="alert"
            tabIndex={-1}
            className="text-sm font-semibold text-warning-text"
          >
            {t("sos.error.raiseFailed")}
          </p>
        )}
      </div>
    ) : (
      <p>{isolateBidi(t("sos.rerouted", { name: rerouted }), rerouted)}</p>
    );

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={t("sos.title")}
      footer={
        rerouted === null ? (
          <>
            {/* The house pattern: ghost dismiss + secondary confirm, and the
                dismiss reuses F36's shipped «ביטול». */}
            <Button variant="ghost" size="md" fullWidthMobile={false} onClick={onClose}>
              {t("rooms.cancel")}
            </Button>
            <Button
              ref={sendRef}
              variant="secondary"
              size="md"
              fullWidthMobile={false}
              loading={busy}
              onClick={() => void send()}
            >
              {t("sos.send")}
            </Button>
          </>
        ) : (
          <Button
            ref={ackRef}
            variant="secondary"
            size="md"
            fullWidthMobile={false}
            onClick={onClose}
          >
            {t("sos.reroutedAck")}
          </Button>
        )
      }
    >
      {body}
    </Modal>
  );
}
