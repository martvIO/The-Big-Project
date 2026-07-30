import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Badge, Card, DateField, EmptyState, Skeleton } from "@boutique/ui";
import { api, errorMessage } from "../api";
import type { OwnerBookingDetail, OwnerBookingRow } from "../api";
import { isolateLtr, statusBadge } from "../lib/booking";
import { jerusalemTime, todayJerusalem } from "../lib/jerusalem";
import { BookingDetail } from "./BookingDetail";

// Mirrors BOOKING_LIST_DEFAULT_LIMIT. Not parity-guarded: the server clamps the
// page itself, so a stale client can only ask for a smaller page, never a bigger
// one. There are deliberately no prev/next controls — a Jerusalem day at pilot
// volume fits fifty rows — and the count line stays regardless, because it is
// the console's only announced list state.
const PAGE_LIMIT = 50;

export function BookingsSection() {
  const { t } = useTranslation();
  const [date, setDate] = useState(todayJerusalem);
  const [rows, setRows] = useState<OwnerBookingRow[] | null>(null);
  const [total, setTotal] = useState(0);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  // Bumped when a mutation moved the booking in time. See onBookingChanged.
  const [reload, setReload] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setRows(null);
    setLoadError(null);
    api
      .listBookings({ date, offset: 0, limit: PAGE_LIMIT })
      .then((result) => {
        if (!cancelled) {
          setRows(result.items);
          setTotal(result.total);
        }
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          // Deliberately NOT setRows([]) — an empty list under the alert would
          // stack the empty-day EmptyState on top of an outage message.
          setLoadError(errorMessage(error));
        }
      });
    return () => {
      cancelled = true;
    };
  }, [date, reload]);

  const loading = rows === null && loadError === null;

  if (selectedId !== null) {
    // An in-panel state swap, the CatalogSection -> DressEditor shape:
    // apps/manage has no router and F15 does not introduce one for one view.
    return (
      <BookingDetail
        bookingId={selectedId}
        onBack={() => setSelectedId(null)}
        onBookingChanged={(next: OwnerBookingDetail) => {
          const previous = rows?.find((booking) => booking.id === next.id);
          if (previous !== undefined && previous.starts_at !== next.starts_at) {
            // A reschedule is the one mutation a patch cannot absorb: list
            // MEMBERSHIP, the server `total` and the server's
            // (starts_at, seat_index) ORDER are all derived from `starts_at`.
            // Patched in place, a cross-day move leaves a phantom row on a list
            // that deliberately prints no date, and the announced count stays
            // wrong. Refetch the day instead of guessing all three.
            setReload((n) => n + 1);
            return;
          }
          // Every other mutation: no refetch. The row is patched from the
          // response, so the two views cannot disagree — same object.
          setRows((current) =>
            current === null
              ? current
              : current.map((booking) => (booking.id === next.id ? next : booking)),
          );
        }}
      />
    );
  }

  return (
    <div className="space-y-6">
      <h2 className="text-lg font-semibold text-ink">{t("booking.heading")}</h2>

      <Card>
        <DateField
          label={t("booking.dateLabel")}
          // A date control is a numeric run; the box keeps its RTL position.
          dir="ltr"
          className="max-w-[200px]"
          value={date}
          // The day filter is required — the console has no all-bookings view
          // (D17) — so a cleared native picker keeps the last date rather than
          // asking the server for `date=`.
          onChange={(event) => {
            if (event.target.value !== "") {
              setDate(event.target.value);
            }
          }}
        />
      </Card>

      {/* The list's single announced region: the count, the loading state and
          the post-mutation focus destination, all in the one place. The shipped
          console announces nothing while loading; F15 closes that for itself by
          reusing the region the count needs anyway (design F-1). */}
      <p
        role="status"
        tabIndex={-1}
        data-testid="bookings-count"
        className="text-sm text-ink-muted"
      >
        {loading
          ? t("booking.listLoading")
          : loadError !== null
            ? ""
            : isolateLtr(t("booking.dayCount", { count: total }), String(total))}
      </p>

      {loadError !== null && (
        // An outage, not a fault of hers: the muted register, and no retry
        // control — re-selecting the date refetches.
        <p role="alert" className="text-sm text-ink-muted">
          {t("booking.loadFailed")}
        </p>
      )}

      {loading && <Skeleton variant="text" lines={4} />}

      {rows !== null && (
        // The Card's own p-6 is NOT overridden: cn() is a plain join, so a
        // consumer p-0 and Card's baked-in p-6 are same-specificity rules and
        // the built stylesheet emits .p-0 first — the override is silently inert
        // (design F-6). Inset dividers are the shipped console shape anyway.
        <Card>
          {rows.length === 0 ? (
            <EmptyState title={t("booking.emptyDayTitle")} body={t("booking.emptyDayBody")} />
          ) : (
            <ul className="divide-y divide-border">
              {rows.map((booking) => {
                const badge = statusBadge(booking.status);
                return (
                  <li key={booking.id}>
                    {/* One affordance per row: the whole row opens the detail.
                        py-4 + text-base clears 44px with no min-h literal. */}
                    <button
                      type="button"
                      className="flex w-full items-start gap-3 py-4 text-start"
                      onClick={() => setSelectedId(booking.id)}
                    >
                      <span className="w-14 shrink-0 font-semibold text-ink">
                        <bdi dir="ltr">{jerusalemTime(booking.starts_at)}</bdi>
                      </span>
                      <span className="min-w-0 grow space-y-1">
                        <span className="flex flex-wrap items-center gap-2">
                          {/* Bare bdi: dir="ltr" on a Hebrew name is itself a
                              bidi defect. */}
                          <bdi className="font-semibold text-ink">{booking.customer_name}</bdi>
                          <Badge variant={badge.variant} data-testid="booking-status">
                            {t(badge.labelKey)}
                          </Badge>
                        </span>
                        <span className="block text-sm text-ink-muted">
                          {booking.appointment_type_name}
                          {booking.attendance_confirmed_at !== null && (
                            // Muted words, never a second Badge — nothing may
                            // compete with the status chip for meaning.
                            <> · {t("booking.attendanceConfirmed")}</>
                          )}
                        </span>
                        {booking.dress_name !== null && (
                          <span className="block text-sm text-ink-muted">
                            <bdi>{booking.dress_name}</bdi>
                          </span>
                        )}
                      </span>
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </Card>
      )}
    </div>
  );
}
