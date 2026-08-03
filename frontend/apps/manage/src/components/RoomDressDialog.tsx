import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Button, Input, Modal, Select } from "@boutique/ui";
import { api } from "../api";
import type { FloorDress, Room } from "../api";

// F36. Bind a gown to the room a bride is standing in — all five roles, no
// ownership check (spec D4): a colleague fetching a second gown for a fitting
// already in progress is the normal case on a shop floor, and binding a dress is
// not a destructive act on the holder's room. `removed_by` on the other control
// is what keeps it accountable.
//
// ⚠ THE CONTROLS ARE THE SHIPPED ONES, NAMED — not "a native <select>". Select
// already carries that decision in its own comment, REQUIRES a `label`, wires
// useId() → htmlFor and applies focusRing. Written as "a native <select>" a
// builder reasonably renders a bare element and loses the label association and
// the focus ring — and axe catches the missing label but NOT the missing ring.
// An ARIA combobox is declined outright: the single most commonly
// mis-implemented widget in the spec, on a legally binding surface.
//
// ⚠ DC-13 / F-11, recorded and NOT fixed here: `Select.label` is typed `string`,
// so an interpolated label cannot be bidi-isolated at all — while `Input.label`
// is typed ReactNode, widened by F17 for exactly this. F36 declines the
// shared-code edit (D15's discipline this run is not to reach into packages/ui
// for a convenience) and instead puts every interpolated value LAST, after an
// em-dash, which is the position a Latin room label cannot visibly reorder from.

interface RoomDressDialogProps {
  open: boolean;
  room: Room;
  onClose: () => void;
  onAdd: (dressId: string, sizeLabel: string | null) => void;
  busy: boolean;
}

export function RoomDressDialog({ open, room, onClose, onAdd, busy }: RoomDressDialogProps) {
  const { t } = useTranslation();

  const [dresses, setDresses] = useState<FloorDress[] | null>(null);
  const [truncated, setTruncated] = useState(false);
  const [filter, setFilter] = useState("");
  const [dressId, setDressId] = useState("");
  const [size, setSize] = useState("");

  useEffect(() => {
    // ONE read per open, and never on the tick (spec D16). Client-side filtering
    // from here on: no ?q=, no debounce, no second request.
    if (!open) {
      return;
    }
    setFilter("");
    setDressId("");
    setSize("");
    let cancelled = false;
    api
      .listFloorDresses()
      .then((list) => {
        if (!cancelled) {
          setDresses(list.dresses);
          setTruncated(list.truncated);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setDresses([]);
          setTruncated(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [open]);

  const needle = filter.trim();
  const matches = (dresses ?? []).filter(
    (dress) => needle === "" || dress.name.includes(needle),
  );
  // DERIVED rather than stored: a filter that drops the chosen gown must not
  // leave a selection pointing at a row nobody can see, and re-deriving is
  // cheaper than an effect that re-selects.
  const chosen = matches.find((dress) => dress.id === dressId) ?? matches[0];
  const sizes = chosen?.sizes ?? [];
  // ⚠ DERIVED for the same reason `chosen` is. Typing in the filter can change
  // `chosen` with no onChange firing, and `size` is reset only by the gown
  // picker's own onChange — so a stored size survived onto a different gown, the
  // picker showed «ללא מידה» while state still held it, and the confirm posted
  // the pair the screen was not showing. The server stores `size_label` verbatim
  // as a permanent snapshot with no lookup against dress_variants, so «סברינה ·
  // 40» would be the record for a gown that comes in no sizes at all.
  const activeSize = sizes.includes(size) ? size : "";

  return (
    <Modal
      open={open}
      onClose={onClose}
      // Value LAST after an em-dash — a `string` prop cannot be bidi-isolated,
      // and last is the one position where a direction flip has nothing after it
      // to reorder past.
      title={t("rooms.dressTitle", { room: room.label })}
      footer={
        <>
          <Button variant="ghost" size="md" fullWidthMobile={false} onClick={onClose}>
            {t("rooms.cancel")}
          </Button>
          {chosen !== undefined && (
            <Button
              variant="secondary"
              size="md"
              fullWidthMobile={false}
              loading={busy}
              onClick={() => onAdd(chosen.id, activeSize === "" ? null : activeSize)}
            >
              {t("rooms.add")}
            </Button>
          )}
        </>
      }
    >
      <div className="space-y-4">
        {dresses !== null && dresses.length === 0 ? (
          // No CTA: three of the five roles cannot reach «שמלות» at all, and
          // pointing them at a door that answers 403 is the trap §2.2 avoids.
          <p className="text-sm text-ink-muted">{t("rooms.dressEmpty")}</p>
        ) : (
          <>
            <Input
              label={t("rooms.dressFilter")}
              value={filter}
              onChange={(event) => setFilter(event.target.value)}
            />
            {truncated && (
              // Names neither a count nor the limit — both are the server's to
              // change without a copy edit — and points at the remedy that is in
              // the dialog with her.
              <p className="text-sm text-ink-muted">{t("rooms.dressTruncated")}</p>
            )}
            {chosen === undefined ? (
              // The two Selects and the confirm are REMOVED, not disabled: a
              // <select> with zero options is a dead control that looks live.
              <p className="text-sm text-ink-muted">{t("rooms.dressNoMatch")}</p>
            ) : (
              <>
                <Select
                  label={t("rooms.dressPick")}
                  className="min-h-11"
                  value={chosen.id}
                  onChange={(event) => {
                    setDressId(event.target.value);
                    setSize("");
                  }}
                >
                  {matches.map((dress) => (
                    <option key={dress.id} value={dress.id}>
                      {dress.name}
                    </option>
                  ))}
                </Select>
                {/* Absent entirely when the gown has no sizes, and the add binds
                    a null size. Not a disabled empty picker. */}
                {sizes.length > 0 && (
                  <Select
                    label={t("rooms.sizePick")}
                    className="min-h-11"
                    value={activeSize}
                    onChange={(event) => setSize(event.target.value)}
                  >
                    {/* Always first and always the default: a sample gown
                        carried in before a size is chosen is D4's stated
                        ordinary case. */}
                    <option value="">{t("rooms.sizeNone")}</option>
                    {sizes.map((label) => (
                      <option key={label} value={label}>
                        {label}
                      </option>
                    ))}
                  </Select>
                )}
              </>
            )}
          </>
        )}
      </div>
    </Modal>
  );
}
