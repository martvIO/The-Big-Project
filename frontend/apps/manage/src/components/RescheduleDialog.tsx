import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Button, Modal, Skeleton, SlotPicker } from "@boutique/ui";
import type { SlotTime } from "@boutique/ui";
import { api } from "../api";
import type { OwnerBookingDetail, OwnerSlotRow } from "../api";
import { bookingErrorText } from "../lib/booking";
import { jerusalemDate, jerusalemIsoDate, jerusalemTime, todayJerusalem } from "../lib/jerusalem";

// One fetch covers the whole window and changing the date filters in memory —
// SlotPicker's shipped contract. Fourteen days is the storefront's shape too.
const WINDOW_DAYS = 14;

// Calendar arithmetic on a bare YYYY-MM-DD, done in UTC so no DST transition can
// move it by an hour and roll the date. Deliberately not a formatter: the result
// is an API bound, never something a human reads.
function addDays(isoDate: string, days: number): string {
  const at = new Date(`${isoDate}T00:00:00Z`);
  at.setUTCDate(at.getUTCDate() + days);
  return at.toISOString().slice(0, 10);
}

export interface RescheduleDialogProps {
  booking: OwnerBookingDetail;
  onClose: () => void;
  onRescheduled: (detail: OwnerBookingDetail) => void;
}

export function RescheduleDialog({ booking, onClose, onRescheduled }: RescheduleDialogProps) {
  const { t } = useTranslation();
  const currentDate = jerusalemIsoDate(booking.starts_at);
  const [date, setDate] = useState(currentDate);
  const [windowFrom, setWindowFrom] = useState(currentDate);
  const [slots, setSlots] = useState<OwnerSlotRow[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  // Pre-selected on the booking's own instant: re-submitting it is free, since
  // the server short-circuits an unchanged reschedule to a no-op 200.
  const [value, setValue] = useState<string | null>(booking.starts_at);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  // The retry control's only job. The list's L-fail can decline one because its
  // DateField sits ABOVE the alert and re-selecting the date refetches; here the
  // alert REPLACES SlotPicker, which owns the DateField, so without this the
  // dialog holds one disabled control and «חזרה» and nothing can clear it.
  const [attempt, setAttempt] = useState(0);

  const windowTo = addDays(windowFrom, WINDOW_DAYS - 1);

  useEffect(() => {
    let cancelled = false;
    setSlots(null);
    setLoadError(null);
    api
      .listManageSlots(windowFrom, windowTo)
      .then((result) => {
        if (!cancelled) {
          setSlots(result.slots);
        }
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setLoadError(bookingErrorText(error, t));
        }
      });
    return () => {
      cancelled = true;
    };
  }, [windowFrom, windowTo, t, attempt]);

  const loading = slots === null && loadError === null;

  const times: SlotTime[] = (slots ?? [])
    .filter((row) => jerusalemIsoDate(row.starts_at) === date)
    .map((row) => ({ value: row.starts_at, label: jerusalemTime(row.starts_at) }));

  // The engine drops full slots, so a capacity-1 target the booking itself
  // occupies never comes back in the grid — and "change my mind" must have a way
  // back (D6). The injected option carries the BARE time and nothing else:
  // SlotPicker renders every label inside <bdi dir="ltr">, so appending
  // «(המועד הנוכחי)» would put Hebrew inside an LTR isolate. It is named in the
  // line above the picker instead.
  if (date === currentDate && !times.some((row) => row.value === booking.starts_at)) {
    times.push({ value: booking.starts_at, label: jerusalemTime(booking.starts_at) });
    times.sort((left, right) => left.value.localeCompare(right.value));
  }

  const submit = async () => {
    if (value === null) {
      return;
    }
    setSubmitting(true);
    setSubmitError(null);
    try {
      onRescheduled(await api.rescheduleBooking(booking.id, value));
    } catch (error) {
      setSubmitError(bookingErrorText(error, t));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Modal
      open
      onClose={onClose}
      title={t("booking.rescheduleTitle")}
      footer={
        <>
          <Button variant="ghost" size="md" onClick={onClose}>
            {t("booking.modalKeep")}
          </Button>
          <Button
            size="md"
            disabled={loading || loadError !== null || value === null || submitting}
            onClick={() => void submit()}
          >
            {t("booking.rescheduleConfirm")}
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <p className="text-sm text-ink-muted">
          {t("booking.rescheduleCurrent")} <bdi dir="ltr">{jerusalemDate(booking.starts_at)}</bdi>{" "}
          · <bdi dir="ltr">{jerusalemTime(booking.starts_at)}</bdi>
        </p>

        {loading ? (
          <Skeleton variant="text" lines={3} />
        ) : loadError !== null ? (
          <div className="space-y-3">
            <p role="alert" className="text-sm text-ink-muted">
              {loadError}
            </p>
            <Button variant="secondary" size="md" onClick={() => setAttempt((n) => n + 1)}>
              {t("booking.retry")}
            </Button>
          </div>
        ) : (
          <SlotPicker
            labels={{
              pickDate: t("booking.pickDate"),
              pickTime: t("booking.pickTime"),
              noSlots: t("booking.noSlots"),
            }}
            date={date}
            // Today because a past date can never hold a target. No `max`: the
            // bookable horizon is a server bound and F15 mirrors no server bound
            // client-side, so a date past it simply materializes no slots.
            min={todayJerusalem()}
            times={times}
            value={value}
            onDateChange={(next) => {
              if (next === "") {
                return;
              }
              setDate(next);
              // A time picked on another date is not a time on this one.
              setValue(null);
              if (next < windowFrom || next > windowTo) {
                setWindowFrom(next);
              }
            }}
            onChange={setValue}
          />
        )}

        {/* This dialog IS the confirm (design P-2): the consequence sits
            directly above the one submit, rather than a second Modal stacking a
            focus trap over a focus trap for a decision she is already reading. */}
        <p className="text-sm text-ink">{t("booking.rescheduleConsequence")}</p>

        {submitError !== null && (
          // The dialog stays OPEN — closing it would throw away the fetch she
          // needs in order to pick again.
          <p role="alert" className="text-sm text-danger">
            {submitError}
          </p>
        )}
      </div>
    </Modal>
  );
}
