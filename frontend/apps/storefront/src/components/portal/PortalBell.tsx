import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Button, Card } from "@boutique/ui";
import { api } from "../../api";
import type { PortalBell as PortalBellData } from "../../api";
import { DATE, WEEKDAY } from "../booking/BookingFacts";

// The bell (design §5). A DISCLOSURE, not a Modal or a popover: the house
// inline-reveal preference, and it spares the focus-trap machinery.
//
// Fetched ONCE on portal mount (pre-decided #18) — no interval, no
// focus-refetch, no websocket. Every event it lists already sent an SMS the same
// second; this is a history list, not the alert channel.

// One key per rendered kind. An unknown or future kind renders NOTHING — a raw
// enum must never reach the screen, and a new backend kind arriving before its
// copy is a row that quietly does not appear rather than a `owner_reschedule`
// on a bride's phone.
const KIND_KEYS: Record<string, string> = {
  confirmation: "portal.bellKindConfirmation",
  reminder: "portal.bellKindReminder",
  owner_cancel: "portal.bellKindOwnerCancel",
  owner_reschedule: "portal.bellKindOwnerReschedule",
  payment_received_no_slot: "portal.bellKindPaymentReceivedNoSlot",
};

const BADGE_CAP = 9;
const PANEL_ID = "portal-bell-panel";

interface PortalBellProps {
  data: PortalBellData | null;
  /** true once the fetch failed — the button stays operable and shows NO badge. */
  failed: boolean;
  onRetry: () => void;
  onOpenBooking: (id: string) => void;
}

export function PortalBell({ data, failed, onRetry, onOpenBooking }: PortalBellProps) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  // ⚠ F-P2: the badge clears only AFTER the seen POST resolves. Clearing on the
  // click paints a read state the server never recorded, and an offline tap
  // would resurrect the badge on her next visit and read as a bug.
  const [seenAcked, setSeenAcked] = useState(false);
  const buttonRef = useRef<HTMLButtonElement | null>(null);
  const headingRef = useRef<HTMLParagraphElement | null>(null);

  useEffect(() => {
    if (open) headingRef.current?.focus();
  }, [open]);

  // NEVER a stale or invented count: a failed fetch shows no badge at all.
  const unread = failed || data === null || seenAcked ? 0 : data.unread_count;

  const toggle = () => {
    if (open) {
      setOpen(false);
      buttonRef.current?.focus();
      return;
    }
    setOpen(true);
    // Nothing was shown, so nothing is marked seen (F-P2's logic).
    if (failed || data === null) return;
    void api
      .portalBellSeen()
      .then(() => {
        setSeenAcked(true);
      })
      .catch(() => {
        // The stamp did not happen, so the badge stays. She sees the truth.
      });
  };

  const items = (data?.items ?? []).filter((item) => item.kind in KIND_KEYS);

  return (
    <div className="flex w-full flex-col gap-3">
      <div className="flex">
        <Button
          ref={buttonRef}
          type="button"
          variant="ghost"
          size="md"
          aria-expanded={open}
          aria-controls={PANEL_ID}
          // The COUNT lives in the accessible name; the visible badge is
          // aria-hidden, so a screen reader hears "3 new" rather than "9+".
          aria-label={
            unread > 0
              ? t("portal.bellLabelUnread", { count: unread })
              : t("portal.bellLabel")
          }
          onClick={toggle}
        >
          <span aria-hidden="true">🔔</span>
          {unread > 0 && (
            <span
              aria-hidden="true"
              className="ms-2 rounded-full bg-gold px-2 py-0.5 text-xs text-ink"
            >
              <bdi dir="ltr">{unread > BADGE_CAP ? `${BADGE_CAP}+` : String(unread)}</bdi>
            </span>
          )}
        </Button>
      </div>

      {open && (
        <Card id={PANEL_ID} className="flex flex-col gap-4 bg-surface-raised">
          {/* The focus destination — the panel's own heading, so a screen reader
              hears what opened rather than an anonymous container. */}
          <p ref={headingRef} tabIndex={-1} className="text-lg font-semibold text-ink">
            {t("portal.bellTitle")}
          </p>

          {failed || data === null ? (
            <>
              {/* `manage.loadFailed` / `manage.retry` reused verbatim — the same
                  failure, the same words. No role="alert": it is reached BY the
                  focus move (the booking dead-end ruling). */}
              <p className="max-w-[60ch] text-base text-ink-muted">{t("manage.loadFailed")}</p>
              <div className="flex">
                <Button variant="secondary" size="md" fullWidthMobile onClick={onRetry}>
                  {t("manage.retry")}
                </Button>
              </div>
            </>
          ) : items.length === 0 ? (
            // A designed quiet, not a bug: an unconfigured-SMS deployment is
            // honestly empty.
            <p className="max-w-[60ch] text-base text-ink-muted">{t("portal.bellEmpty")}</p>
          ) : (
            <ul className="flex flex-col gap-3">
              {items.map((item) => {
                const when = new Date(item.starts_at);
                return (
                  <li key={item.id}>
                    <button
                      type="button"
                      className="flex min-h-[44px] w-full flex-col gap-1 text-start"
                      onClick={() => {
                        setOpen(false);
                        onOpenBooking(item.booking_id);
                      }}
                    >
                      <span className="font-semibold text-ink">{t(KIND_KEYS[item.kind])}</span>
                      <span className="text-sm text-ink-muted">
                        <bdi>{item.appointment_type_name}</bdi>{" "}
                        <span aria-hidden="true">·</span> {WEEKDAY.format(when)},{" "}
                        <bdi dir="ltr">{DATE.format(when)}</bdi>
                      </span>
                    </button>
                  </li>
                );
              })}
            </ul>
          )}

          <div className="flex">
            <Button variant="ghost" size="md" onClick={toggle}>
              {t("portal.bellClose")}
            </Button>
          </div>
        </Card>
      )}
    </div>
  );
}
