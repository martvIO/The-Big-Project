import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Button, Input, Modal, Toggle } from "@boutique/ui";
import { api, ApiError } from "../api";
import { isolateBidi } from "../lib/booking";
import type { Room, UpdateRoomRequest } from "../api";
import { MAX_ROOM_LABEL_LENGTH, MAX_SORT_ORDER } from "../validation";

// F36. The owner's «חדר 1 / חדר 2 / הבמה», typed once and never again — add,
// rename, reorder, deactivate and delete-with-confirm, for owner and
// shift_manager only (P-8). Its trigger lives on RoomsPanel and does not exist
// for the other three roles, so this whole component is elevated-only by
// construction rather than by a check inside it.
//
// ⚠ THE SEED-ONCE CONTRACT, because this dialog lives inside a component that
// repaints every five seconds. There is no registry list endpoint — the rows
// come from the polled `rooms` prop — and `holdRef` does not help: it consumes
// ONE tick on pointerdown and typing fires no pointer events. A tick landing
// while the owner is halfway through «חדר 4» would re-render the rows from
// server data, and this feature's "patch from the server's row, never
// optimistic" discipline makes that a RESET rather than a merge. So the rows are
// seeded from `rooms` ONCE at open, are never re-read from the poll while open,
// and are re-seeded on close and from each successful write's own response.
//
// ⚠ Do NOT reach for poll.pause(). The pause control's accessible name would
// then announce a state the owner did not choose (F57's D12), and suppressing
// the poll while a dialog is open freezes the freshness stamp with nothing on
// screen to explain the freeze — «אין עדכון מאז» renders after a FAILED tick,
// not a suppressed one, so the panel would simply stop being current and say
// nothing.

interface Draft {
  id: string;
  label: string;
  // A STRING, not a number: an <input type="number"> mid-edit legitimately holds
  // "-", "" and "1e3", and Number("") is 0 — which would silently reorder a row
  // she was in the middle of clearing.
  sortOrder: string;
  isActive: boolean;
}

interface FieldErrors {
  label?: string;
  order?: string;
}

interface RoomsRegistryDialogProps {
  open: boolean;
  onClose: () => void;
  rooms: Room[];
  onRooms: (next: Room[]) => void;
  mutate: (fn: () => Promise<void>) => Promise<unknown>;
}

function draftOf(room: Room): Draft {
  return {
    id: room.id,
    label: room.label,
    sortOrder: String(room.sort_order),
    isActive: room.is_active,
  };
}

// The mirrored bounds, applied before the request rather than after the refusal:
// the server answers a house-shape 400 whose message is ENGLISH, and this
// console is Hebrew-only. Client-side validation is what keeps that message
// unreachable, and the two rules are exactly the server's two.
function validate(label: string, sortOrder: string): FieldErrors {
  const errors: FieldErrors = {};
  const stripped = label.trim();
  if (stripped === "") {
    errors.label = "rooms.labelRequired";
  } else if (stripped.length > MAX_ROOM_LABEL_LENGTH) {
    errors.label = "rooms.labelTooLong";
  }
  const order = Number(sortOrder);
  if (sortOrder.trim() === "" || !Number.isInteger(order) || Math.abs(order) > MAX_SORT_ORDER) {
    errors.order = "rooms.orderRange";
  }
  return errors;
}

export function RoomsRegistryDialog({
  open,
  onClose,
  rooms,
  onRooms,
  mutate,
}: RoomsRegistryDialogProps) {
  const { t } = useTranslation();

  const [drafts, setDrafts] = useState<Draft[]>([]);
  const [errors, setErrors] = useState<Record<string, FieldErrors>>({});
  const [addLabel, setAddLabel] = useState("");
  const [addError, setAddError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [cue, setCue] = useState("");
  // The room awaiting confirmation, plus whatever the server said about the last
  // attempt on it. `value` is the ONE interpolated run — the occupant's name —
  // which has to render inside a bare <bdi>.
  const [confirming, setConfirming] = useState<Draft | null>(null);
  const [confirmError, setConfirmError] = useState<{ text: string; value: string | null } | null>(
    null,
  );

  useEffect(() => {
    // ONCE, at open. `rooms` is deliberately NOT a dependency: that omission IS
    // the contract above, not an oversight.
    if (!open) {
      return;
    }
    setDrafts(rooms.map(draftOf));
    setErrors({});
    setAddLabel("");
    setAddError(null);
    setCue("");
    setConfirming(null);
    setConfirmError(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  const message = (error: unknown): { text: string; value: string | null } => {
    if (error instanceof ApiError && error.status === 409) {
      const name = error.details?.staff_display_name;
      return name === undefined
        ? { text: t("rooms.error.deleteOccupiedUnknown"), value: null }
        : { text: t("rooms.error.deleteOccupied", { name }), value: name };
    }
    if (error instanceof ApiError && error.status === 404) {
      return { text: t("rooms.error.notFound"), value: null };
    }
    // Unreachable through the two mirrored bounds above; a 5xx or a dropped
    // request lands here, in the outage register, on a SHIPPED string rather
    // than errorMessage(error) leaking the server's English.
    return { text: t("staff.loadFailed"), value: null };
  };

  const save = (draft: Draft) => {
    const found = validate(draft.label, draft.sortOrder);
    if (found.label !== undefined || found.order !== undefined) {
      setErrors((current) => ({ ...current, [draft.id]: found }));
      return;
    }
    setErrors((current) => ({ ...current, [draft.id]: {} }));
    setBusyId(draft.id);
    void mutate(async () => {
      const patched = await api.updateRoom(draft.id, {
        label: draft.label.trim(),
        sort_order: Number(draft.sortOrder),
      });
      onRooms(rooms.map((room) => (room.id === patched.id ? patched : room)));
      setDrafts((current) => current.map((row) => (row.id === patched.id ? draftOf(patched) : row)));
      setCue(t("common.saved"));
    }).then((failure) => {
      setBusyId(null);
      if (failure !== null) {
        setCue(message(failure).text);
      }
    });
  };

  // The Toggle and «מחיקה» act IMMEDIATELY — each is a single reversible or
  // confirmed fact, and F57's break toggle is the precedent. The label and the
  // order need an explicit «שמירה», because typing has no natural commit point.
  const setActive = (draft: Draft, isActive: boolean) => {
    setBusyId(draft.id);
    const body: UpdateRoomRequest = { is_active: isActive };
    void mutate(async () => {
      const patched = await api.updateRoom(draft.id, body);
      onRooms(rooms.map((room) => (room.id === patched.id ? patched : room)));
      setDrafts((current) => current.map((row) => (row.id === patched.id ? draftOf(patched) : row)));
      setCue(t("common.saved"));
    }).then((failure) => {
      setBusyId(null);
      if (failure !== null) {
        setCue(message(failure).text);
      }
    });
  };

  const add = () => {
    const found = validate(addLabel, "0");
    if (found.label !== undefined) {
      setAddError(found.label);
      return;
    }
    setAddError(null);
    setBusyId("add");
    void mutate(async () => {
      const created = await api.createRoom({ label: addLabel.trim() });
      onRooms([...rooms, created]);
      setDrafts((current) => [...current, draftOf(created)]);
      setAddLabel("");
      setCue(t("rooms.addedCue"));
    }).then((failure) => {
      setBusyId(null);
      if (failure !== null) {
        setCue(message(failure).text);
      }
    });
  };

  const remove = (draft: Draft) => {
    setBusyId(draft.id);
    setConfirmError(null);
    void mutate(async () => {
      await api.deleteRoom(draft.id);
      onRooms(rooms.filter((room) => room.id !== draft.id));
      setDrafts((current) => current.filter((row) => row.id !== draft.id));
      setConfirming(null);
      setCue(t("rooms.deletedCue"));
    }).then((failure) => {
      setBusyId(null);
      if (failure === null) {
        return;
      }
      if (failure instanceof ApiError && failure.status === 409) {
        // The confirm STAYS: a retry two minutes later is legitimate, and
        // closing would make her walk the whole path again.
        setConfirmError(message(failure));
        return;
      }
      setConfirming(null);
      setCue(message(failure).text);
    });
  };

  const edit = (id: string, patch: Partial<Draft>) => {
    setDrafts((current) => current.map((row) => (row.id === id ? { ...row, ...patch } : row)));
  };

  return (
    <>
      <Modal
        open={open}
        onClose={onClose}
        title={t("rooms.manageTitle")}
        footer={
          <Button variant="ghost" size="md" fullWidthMobile={false} onClick={onClose}>
            {t("rooms.close")}
          </Button>
        }
      >
        {/* ⚠ A SECOND live region on the screen, and it is only defensible
            because it lives inside the top layer: a live region outside an open
            modal is not reliably announced while the dialog holds the
            accessibility tree, and the whole point of a cue is that it is heard.
            The rule it must not erode is F57's D12 — one named control per
            AUTO-UPDATING region — and nothing writes here but her own saves.

            ⚠ DC-9 asked for this to sit with the save it confirms rather than at
            the top of a twenty-row scroll, OR for the top to be argued. The top
            is argued, on two grounds: a live region has to exist in the DOM
            before its text changes or the change is not announced at all, so a
            region that moves between rows is a region that is not read; and the
            announcement is independent of scroll position, while the VISUAL
            confirmation of a row save is the row itself re-rendering from the
            server's own response. */}
        <p data-testid="registry-cue" role="status" className="text-sm text-ink-muted">
          {cue}
        </p>

        <div className="mt-4 space-y-6">
          {drafts.map((draft) => {
            const labelError = errors[draft.id]?.label;
            const orderError = errors[draft.id]?.order;
            return (
            <div key={draft.id} data-registry-row data-testid="registry-row" className="space-y-3">
              <Input
                label={t("rooms.label")}
                value={draft.label}
                maxLength={MAX_ROOM_LABEL_LENGTH}
                error={labelError === undefined ? undefined : t(labelError)}
                onChange={(event) => edit(draft.id, { label: event.target.value })}
              />
              <div className="flex flex-wrap items-end gap-3">
                {/* ⚠ REORDER IS THIS LABELLED NUMBER FIELD AND NEVER
                    DRAG-AND-DROP (spec D18). Drag's most common implementation
                    is a WCAG 2.1.1 keyboard failure that axe cannot see — the
                    same ladder rung and the same legal reasoning D16 uses to
                    refuse an ARIA combobox. Negatives are legal and useful: they
                    move a row to the front without renumbering the rest, which
                    is the whole point of D1's symmetric bound. */}
                <Input
                  label={t("rooms.order")}
                  type="number"
                  inputMode="numeric"
                  min={-MAX_SORT_ORDER}
                  max={MAX_SORT_ORDER}
                  className="w-28"
                  value={draft.sortOrder}
                  error={orderError === undefined ? undefined : t(orderError)}
                  onChange={(event) => edit(draft.id, { sortOrder: event.target.value })}
                />
                <Toggle
                  label={t("rooms.active")}
                  checked={draft.isActive}
                  disabled={busyId === draft.id}
                  onCheckedChange={(checked) => setActive(draft, checked)}
                />
              </div>
              <div className="flex flex-wrap justify-end gap-3">
                {/* ALWAYS enabled: tapping it on a clean row is a PATCH that
                    changes nothing and answers 200, which is cheaper than
                    dirty-tracking three fields and matches this codebase's
                    F-noop philosophy everywhere else. */}
                <Button
                  variant="secondary"
                  size="md"
                  fullWidthMobile={false}
                  loading={busyId === draft.id}
                  onClick={() => save(draft)}
                >
                  {t("rooms.save")}
                </Button>
                {/* The ONLY danger control in the feature, and it is a CHOICE
                    rather than a report — which is exactly why the refusals
                    below are not red. */}
                <Button
                  variant="danger"
                  size="md"
                  fullWidthMobile={false}
                  onClick={() => {
                    setConfirmError(null);
                    setConfirming(draft);
                  }}
                >
                  {t("rooms.delete")}
                </Button>
              </div>
            </div>
            );
          })}

          {/* The add row is LAST, because a new room defaults to sort_order 0
              and the tiebreak is created_at — so it lands at the end of the zero
              group, which is where the list will show it. */}
          <div data-testid="registry-add" className="space-y-3 border-t border-border pt-6">
            <Input
              label={t("rooms.label")}
              value={addLabel}
              maxLength={MAX_ROOM_LABEL_LENGTH}
              error={addError === null ? undefined : t(addError)}
              onChange={(event) => setAddLabel(event.target.value)}
            />
            <div className="flex justify-end">
              <Button
                variant="secondary"
                size="md"
                fullWidthMobile={false}
                loading={busyId === "add"}
                onClick={add}
              >
                {t("rooms.add")}
              </Button>
            </div>
          </div>
        </div>
      </Modal>

      {/* manage-restyle.md's shipped destructive pattern, unchanged: a danger
          trigger opening a NESTED Modal with a ghost dismiss and a danger
          confirm. Modal's own comment anticipates two mounted at once, native
          <dialog> stacks in the top layer, Esc closes the topmost only, and the
          trap comes for free — where the storefront's inline two-step would
          bring a hand-rolled focus move whose test is already on the
          known_flaky list. */}
      <Modal
        open={confirming !== null}
        onClose={() => setConfirming(null)}
        title={t("rooms.deleteConfirm")}
        footer={
          <>
            <Button
              variant="ghost"
              size="md"
              fullWidthMobile={false}
              onClick={() => setConfirming(null)}
            >
              {t("rooms.cancel")}
            </Button>
            <Button
              variant="danger"
              size="md"
              fullWidthMobile={false}
              loading={busyId === confirming?.id}
              onClick={() => {
                if (confirming !== null) {
                  remove(confirming);
                }
              }}
            >
              {t("rooms.delete")}
            </Button>
          </>
        }
      >
        {/* The room label is its OWN element here rather than interpolated into
            the title: Modal.title is typed `string`, so a label inside it could
            not be bidi-isolated at all — and unlike every other unisolatable
            interpolation in this feature the value would sit MID-STRING with a
            «?» after it, the one position where a Latin-script room label
            reorders visibly. */}
        <p className="font-semibold break-words text-ink">
          <bdi>{confirming?.label}</bdi>
        </p>
        {/* States the one rule she can hit, so the refusal below is expected
            rather than a surprise. */}
        <p className="mt-2 text-sm text-ink-muted">{t("rooms.deleteConfirmBody")}</p>
        {confirmError !== null && (
          <p role="alert" className="mt-2 text-sm font-semibold text-warning-text">
            {confirmError.value === null
              ? confirmError.text
              : isolateBidi(confirmError.text, confirmError.value)}
          </p>
        )}
      </Modal>
    </>
  );
}
