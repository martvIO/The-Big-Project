import { useTranslation } from "react-i18next";
import { Badge, Button, Card, Skeleton, VisuallyHidden } from "@boutique/ui";
import type { PortalBookingRow, PortalBookings } from "../../api";
import { DATE, TIME, WEEKDAY } from "../booking/BookingFacts";
import { PortalEmpty } from "./PortalEmpty";

// "My Bookings" (design §3). Rows are whole-row buttons; the ORDER IS THE
// SERVER'S — upcoming ASC, past DESC — and this component re-sorts nothing,
// because the split boundary is a clock and a clock in the browser moves per
// device.

const PENDING_PAYMENT = "pending_payment";
const CANCELLED = "cancelled";

// Badges only where the status demands action or explains an absence (design
// P3). A confirmed upcoming row carries NONE — the default state needs no
// label — and `completed` / `no_show` carry none either: the boutique's
// attendance bookkeeping is not rendered back at her.
function statusBadgeKey(status: string): string | null {
  if (status === PENDING_PAYMENT) return "portal.statusAwaitingPayment";
  if (status === CANCELLED) return "portal.statusCancelled";
  return null;
}

function BookingRow({ row, onOpen }: { row: PortalBookingRow; onOpen: (id: string) => void }) {
  const { t } = useTranslation();
  const when = new Date(row.starts_at);
  const badgeKey = statusBadgeKey(row.status);

  return (
    <Card className="p-0">
      <button
        type="button"
        // min-h-[44px] is the house touch floor (F-W1): `sm` controls are 36px
        // and fail it, so nothing in this feature is `sm`.
        className="flex min-h-[44px] w-full flex-col gap-1 p-4 text-start"
        onClick={() => {
          onOpen(row.id);
        }}
      >
        <span className="text-base text-ink">
          {WEEKDAY.format(when)}, <bdi dir="ltr">{DATE.format(when)}</bdi>{" "}
          <span aria-hidden="true">·</span> <bdi dir="ltr">{TIME.format(when)}</bdi>
        </span>
        <span className="text-sm text-ink-muted">
          <bdi>{row.appointment_type_name}</bdi>
          {row.dress_name !== null && (
            <>
              {" "}
              <span aria-hidden="true">·</span> <bdi>{row.dress_name}</bdi>
              {row.dress_size !== null && (
                <>
                  , {t("booking.confirmDress")} <bdi>{row.dress_size}</bdi>
                </>
              )}
            </>
          )}
        </span>
        {badgeKey !== null && (
          <span className="pt-1">
            {/* neutral on BOTH: a cancelled appointment is a fact, not an alarm,
                and danger is reserved for the click that destroys. */}
            <Badge variant="neutral">{t(badgeKey)}</Badge>
          </span>
        )}
      </button>
    </Card>
  );
}

interface PortalBookingListProps {
  data: PortalBookings | null;
  loading: boolean;
  failed: boolean;
  onRetry: () => void;
  onOpen: (id: string) => void;
}

export function PortalBookingList({
  data,
  loading,
  failed,
  onRetry,
  onOpen,
}: PortalBookingListProps) {
  const { t } = useTranslation();

  if (loading) {
    return (
      <div className="flex flex-col gap-4">
        {/* R30's nested shape — aria-busy on a plain div is announced by neither
            VoiceOver nor NVDA. */}
        <VisuallyHidden>
          <span role="status">{t("portal.loadingBookings")}</span>
        </VisuallyHidden>
        <Card className="flex flex-col gap-4" data-testid="portal-loading">
          <Skeleton variant="text" lines={2} />
          <Skeleton variant="text" lines={2} />
        </Card>
      </div>
    );
  }

  if (failed || data === null) {
    return (
      <div className="flex flex-col gap-4">
        {/* `manage.loadFailed` / `manage.retry` REUSED verbatim: the same
            failure, the same words (design §3). */}
        <p role="alert" className="max-w-[60ch] text-base text-ink-muted">
          {t("manage.loadFailed")}
        </p>
        <div className="flex">
          <Button variant="secondary" size="md" fullWidthMobile onClick={onRetry}>
            {t("manage.retry")}
          </Button>
        </div>
      </div>
    );
  }

  // Both sections empty is the SAME screen the login's no-bookings refusal
  // renders (design P2) — one component, no enumeration surface.
  if (data.upcoming.length === 0 && data.past.length === 0) return <PortalEmpty />;

  return (
    <div className="flex flex-col gap-6">
      <section className="flex flex-col gap-3">
        <h2 className="text-lg font-semibold text-ink">{t("portal.upcoming")}</h2>
        {data.upcoming.length === 0 ? (
          // Only shown because the OTHER section has rows — two empty sections
          // are the whole-screen empty state above.
          <p className="text-base text-ink-muted">{t("portal.upcomingEmpty")}</p>
        ) : (
          data.upcoming.map((row) => <BookingRow key={row.id} row={row} onOpen={onOpen} />)
        )}
      </section>

      <section className="flex flex-col gap-3">
        <h2 className="text-lg font-semibold text-ink">{t("portal.past")}</h2>
        {data.past.length === 0 ? (
          <p className="text-base text-ink-muted">{t("portal.pastEmpty")}</p>
        ) : (
          data.past.map((row) => <BookingRow key={row.id} row={row} onOpen={onOpen} />)
        )}
      </section>
    </div>
  );
}
