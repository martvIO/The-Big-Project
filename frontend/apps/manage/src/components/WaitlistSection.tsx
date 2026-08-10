import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Badge, Button, Card, DateField, EmptyState, Skeleton, VisuallyHidden } from "@boutique/ui";
import { api } from "../api";
import type { BookingWaitlistRow } from "../api";
import { isolateLtr } from "../lib/booking";
import {
  jerusalemIsoDate,
  jerusalemTime,
  plainDate,
  plainDayMonth,
  todayJerusalem,
} from "../lib/jerusalem";

// F22's console section (design §4). NOT `WaitlistPanel` — that is F58's
// walk-in queue on the floor (F-W2); this one lists the BOOKING waitlist.
//
// Simple fetch-on-mount + refetch-on-mutate; deliberately NO `usePoll` — a
// waitlist changes at human speed and this table carries no freshness claim.
// The sections that poll (board, floor) poll because brides physically move.
//
// Row order IS the position (D1): `(day, created_at)` from the server, top row
// next in line. Rendered as given, never re-sorted, no position column.

// The badge speaks Hebrew, never the raw wire value; `offered` is F23-era and
// ships now so the badge never falls back to English.
const STATUS_KEY: Record<string, string> = {
  waiting: "bookingWaitlist.statusWaiting",
  offered: "bookingWaitlist.statusOffered",
};

// F23 P4. `neutral` was F22's placeholder for a status that could not yet
// occur. Now that it can, the in-flight row must separate from the merely
// waiting ones — an owner scanning to clear a day is one click from taking a
// slot back off a bride who is reading her SMS about it.
const STATUS_VARIANT: Record<string, "neutral" | "warning"> = {
  offered: "warning",
};

// he-IL short weekday for the day column — the design's «ה׳ 20.8» shape rides
// plainDate for the numerals, so no Date object ever meets the wire date.
const WEEKDAY = new Intl.DateTimeFormat("he-IL", { weekday: "short", timeZone: "Asia/Jerusalem" });

function weekdayOf(isoDay: string): string {
  // Noon UTC is the same Jerusalem calendar day everywhere — the storefront's
  // own trick, so the weekday can never straddle midnight.
  return WEEKDAY.format(new Date(`${isoDay}T12:00:00Z`));
}

/**
 * The offer column (design §4) — the two instants and NOTHING else.
 *
 * ⚠ It does not tick, and it must never start. The deadline is a fact the
 * server owns, not a timer: R1 removed countdowns from the storefront's offer
 * page for three prior rulings and a legal gate, and an owner's table is the
 * other place one would have been tempting. There is also no cascade history
 * here — no offer counter, no expiry log, no per-entry trail. The audit trail
 * lives in `audit_log`; the one thing this row owes an owner is whether anyone
 * is holding the slot right now, and until when.
 */
function OfferCell({
  startsAt,
  expiresAt,
}: {
  startsAt: string | null;
  expiresAt: string | null;
}) {
  const { t } = useTranslation();
  if (startsAt === null) return <>—</>;
  return (
    <div className="flex flex-col gap-1">
      <span className="text-base">
        {weekdayOf(jerusalemIsoDate(startsAt))}{" "}
        <bdi dir="ltr">{plainDayMonth(jerusalemIsoDate(startsAt))}</bdi>{" "}
        <bdi dir="ltr">{jerusalemTime(startsAt)}</bdi>
      </span>
      {expiresAt !== null && (
        <span className="text-sm text-ink-muted">
          {t("bookingWaitlist.offerUntil")} <bdi dir="ltr">{jerusalemTime(expiresAt)}</bdi>
        </span>
      )}
    </div>
  );
}

export function WaitlistSection() {
  const { t } = useTranslation();
  // The Jerusalem today, once at mount — the filter's default (design §4).
  const [day, setDay] = useState(todayJerusalem);
  // null = NOT YET LOADED. Never [] on failure, which would stack an empty
  // state under the outage alert (the CustomersSection rule).
  const [rows, setRows] = useState<BookingWaitlistRow[] | null>(null);
  const [loadError, setLoadError] = useState(false);
  // The armed row — at most ONE control is in its danger phase at a time, so a
  // double-armed table cannot cancel the wrong woman.
  const [confirming, setConfirming] = useState<string | null>(null);
  const [cancelling, setCancelling] = useState(false);
  // The status region's discrete event (R16): set on success, cleared on the
  // next arm — never per keystroke, never per poll (there is no poll).
  const [announce, setAnnounce] = useState("");

  const fetchList = useCallback(async (forDay: string) => {
    setRows(null);
    setLoadError(false);
    try {
      const listed = await api.getBookingWaitlist(forDay === "" ? undefined : forDay);
      setRows(listed?.entries ?? []);
    } catch {
      setLoadError(true);
    }
  }, []);

  useEffect(() => {
    void fetchList(day);
  }, [day, fetchList]);

  const cancel = async (entryId: string) => {
    if (cancelling) return;
    setCancelling(true);
    try {
      await api.cancelBookingWaitlistEntry(entryId);
      setAnnounce(t("bookingWaitlist.cancelled"));
      setConfirming(null);
      // Refetch, never patch: the server's order is the position and a second
      // entry may have moved up.
      await fetchList(day);
    } catch {
      // The row stays; the honest failure is the load path's own line on the
      // next interaction. Reverting the arm is the one thing owed here.
      setConfirming(null);
    }
    setCancelling(false);
  };

  const loading = rows === null && !loadError;

  return (
    <div className="space-y-6">
      <h2 className="text-lg font-semibold text-ink">{t("nav.bookingWaitlist")}</h2>

      <Card>
        <DateField
          label={t("bookingWaitlist.dayFilter")}
          help={t("bookingWaitlist.dayFilterHint")}
          dir="ltr"
          value={day}
          onChange={(event) => {
            setDay(event.target.value);
          }}
          className="max-w-[200px]"
        />
      </Card>

      {loading && (
        <Card className="flex flex-col gap-4">
          <VisuallyHidden>
            <span role="status">{t("bookingWaitlist.loading")}</span>
          </VisuallyHidden>
          <Skeleton variant="text" lines={3} />
        </Card>
      )}

      {loadError && (
        <Card className="flex flex-col items-start gap-3">
          <p role="alert" className="text-base text-ink-muted">
            {t("bookingWaitlist.loadFailed")}
          </p>
          <Button variant="secondary" onClick={() => void fetchList(day)}>
            {t("bookingWaitlist.retry")}
          </Button>
        </Card>
      )}

      {rows !== null && rows.length === 0 && (
        <Card>
          {day === "" ? (
            <EmptyState
              title={t("bookingWaitlist.emptyTitle")}
              body={t("bookingWaitlist.emptyBody")}
            />
          ) : (
            // A date filter is set: the day may simply have no entries, and
            // the day-one empty copy would misread as "the feature is unused".
            <p className="py-8 text-center text-base text-ink-muted">
              {t("bookingWaitlist.emptyFiltered")}
            </p>
          )}
        </Card>
      )}

      {rows !== null && rows.length > 0 && (
        // The table scrolls inside its own container at narrow widths; the
        // page never scrolls sideways.
        <Card className="overflow-x-auto">
          <table className="w-full text-base">
            <thead>
              <tr className="text-start text-sm text-ink-muted">
                <th className="px-2 py-2 text-start font-normal">{t("bookingWaitlist.colDay")}</th>
                <th className="px-2 py-2 text-start font-normal">{t("bookingWaitlist.colType")}</th>
                <th className="px-2 py-2 text-start font-normal">
                  {t("bookingWaitlist.colCustomer")}
                </th>
                <th className="px-2 py-2 text-start font-normal">
                  {t("bookingWaitlist.colStatus")}
                </th>
                <th className="px-2 py-2 text-start font-normal">
                  {t("bookingWaitlist.colOffer")}
                </th>
                <th className="px-2 py-2 text-start font-normal">
                  {t("bookingWaitlist.colJoined")}
                </th>
                <th className="px-2 py-2" />
              </tr>
            </thead>
            <tbody>
              {rows.map((entry) => (
                <tr key={entry.id} className="border-t border-border">
                  <td className="px-2 py-3">
                    {weekdayOf(entry.day)} <bdi dir="ltr">{plainDate(entry.day)}</bdi>
                  </td>
                  <td className="px-2 py-3">{entry.appointment_type_name ?? "—"}</td>
                  <td className="px-2 py-3">
                    {entry.customer_name ?? isolateLtr(entry.phone, entry.phone)}
                  </td>
                  <td className="px-2 py-3">
                    <Badge variant={STATUS_VARIANT[entry.status] ?? "neutral"}>
                      {t(STATUS_KEY[entry.status] ?? entry.status)}
                    </Badge>
                  </td>
                  <td className="px-2 py-3">
                    <OfferCell
                      startsAt={entry.offer_starts_at}
                      expiresAt={entry.offer_expires_at}
                    />
                  </td>
                  <td className="px-2 py-3">
                    <bdi dir="ltr">{jerusalemTime(entry.created_at)}</bdi>
                  </td>
                  <td className="px-2 py-3 text-end">
                    {confirming === entry.id ? (
                      // The in-place swap (P3): same slot, danger variant, and
                      // Escape or a click elsewhere (blur) reverts. min-h-[44px]
                      // because Button sm's box is 36px — under the touch floor
                      // (F-W1).
                      <Button
                        variant="danger"
                        size="sm"
                        className="min-h-[44px]"
                        loading={cancelling}
                        autoFocus
                        onBlur={() => {
                          if (!cancelling) setConfirming(null);
                        }}
                        onKeyDown={(event) => {
                          if (event.key === "Escape") setConfirming(null);
                        }}
                        onClick={() => void cancel(entry.id)}
                      >
                        {/* An `offered` row is a live offer a bride may be
                            reading right now, so its danger label names the
                            consequence rather than the generic action. */}
                        {t(
                          entry.status === "offered"
                            ? "bookingWaitlist.cancelOfferedConfirm"
                            : "bookingWaitlist.cancelConfirm",
                        )}
                      </Button>
                    ) : (
                      <Button
                        variant="secondary"
                        size="sm"
                        className="min-h-[44px]"
                        onClick={() => {
                          setAnnounce("");
                          setConfirming(entry.id);
                        }}
                      >
                        {t("bookingWaitlist.cancel")}
                      </Button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}

      <VisuallyHidden>
        <span role="status" data-testid="waitlist-section-status">
          {announce}
        </span>
      </VisuallyHidden>
    </div>
  );
}
