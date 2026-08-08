import { useId, useState } from "react";
import { useTranslation } from "react-i18next";
import { Badge, Button, Modal, Skeleton, cn, focusRing } from "@boutique/ui";
import { api, type StaffNotification } from "../api";
import { jerusalemDate, jerusalemIsoDate, jerusalemTime, todayJerusalem } from "../lib/jerusalem";
import { useSos } from "../lib/sos-context";

/**
 * The «התראות» header control and the panel it opens.
 *
 * ⚠ **NO POLL OF ITS OWN, AND THAT IS THE FEATURE.** The count arrives on the
 * SOS tick's payload — the console's only app-wide loop — so there is no
 * `usePoll`, no `setInterval` and no fetch-on-mount anywhere in this file. The
 * list behind the count is fetched only when the PANEL opens: twenty rows are
 * not worth an app-wide read every five seconds.
 *
 * ⚠ **NO CUSTOMER DATUM EVER REACHES THIS SCREEN.** The server does not emit
 * one (the row carries two staff ids, a kind and two timestamps), and the copy
 * has no slot for one. A row says WHO DID WHAT TO YOU; the floor screen, under
 * its own audience rules, says who she is.
 *
 * ⚠ **The count lives in the ACCESSIBLE NAME and nowhere else.** No
 * `role="status"`, no `aria-live`, no `aria-expanded`, no `aria-haspopup`: a
 * five-second-cadence live region narrating a count is hostile, a modal dialog
 * is not a disclosure, and bare `aria-haspopup` means "menu", which this is not.
 * The badge is `aria-hidden` and caps at «9+» while the name stays exact.
 */

const BADGE_CAP = 9;

// Kinds this console can render. An UNKNOWN kind is skipped silently rather than
// rendered raw, so a server shipped ahead of a client degrades to a missing row
// and never to «sos_targeted» on a staffer's screen.
const KIND_COPY: Record<string, string> = {
  dispatch_assigned: "bell.kindDispatch",
  room_handed_over: "bell.kindHandover",
  sos_targeted: "bell.kindSos",
};

// `sos_targeted` rows have NO destination: the live surface is F37's overlay,
// which owns itself. A row that looked tappable and only marked itself read
// would be an affordance that lies.
const NAVIGATES = new Set(["dispatch_assigned", "room_handed_over"]);

export function NotificationBell({ onOpenFloor }: { onOpenFloor: () => void }) {
  const { t } = useTranslation();
  const { unreadNotifications, markRead } = useSos();

  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<StaffNotification[] | null>(null);
  const [loadFailed, setLoadFailed] = useState(false);
  const [markFailed, setMarkFailed] = useState(false);
  const emptyId = useId();

  // The count the BADGE renders. Optimistically zeroed by a mark and rolled back
  // on rejection, so the number on screen answers the tap rather than the last
  // tick — the provider only ever publishes what the server said.
  const [optimistic, setOptimistic] = useState<number | null>(null);
  const count = optimistic ?? unreadNotifications;

  const load = async () => {
    setLoadFailed(false);
    setItems(null);
    try {
      setItems((await api.listNotifications()).items);
    } catch {
      // No state left stale: `items` stays null so the panel renders F1 rather
      // than a half-populated list under an error line.
      setLoadFailed(true);
    }
  };

  const openPanel = () => {
    setOpen(true);
    setMarkFailed(false);
    void load();
  };

  const closePanel = () => {
    setOpen(false);
    setOptimistic(null);
  };

  const mark = async (ids: string[]) => {
    if (ids.length === 0) {
      return true;
    }
    setMarkFailed(false);
    const before = items;
    const read = new Set(ids);
    const at = new Date().toISOString();
    setOptimistic(Math.max(0, count - ids.length));
    setItems((current) =>
      current === null
        ? current
        : current.map((one) => (read.has(one.id) && one.read_at === null ? { ...one, read_at: at } : one)),
    );
    const failure = await markRead(ids);
    if (failure !== null) {
      // Roll BOTH back: the badge returns and the rows go back to unread, which
      // is what makes the «חדש» marker and the count agree again.
      setOptimistic(null);
      setItems(before);
      setMarkFailed(true);
      return false;
    }
    setOptimistic(null);
    return true;
  };

  // §3's order, and it is an order rather than a set. `close()` synchronously
  // returns focus to the bell, so the move to the section must come AFTER it —
  // otherwise she lands on a chrome button above a section she did not ask for.
  const openRow = async (row: StaffNotification) => {
    if (!NAVIGATES.has(row.kind)) {
      return;
    }
    if (!(await mark([row.id]))) {
      return;
    }
    onOpenFloor();
    closePanel();
    document.getElementById("console-main")?.focus();
  };

  const rendered = (items ?? []).filter((one) => one.kind in KIND_COPY);
  const unreadOnPage = rendered.filter((one) => one.read_at === null).map((one) => one.id);

  return (
    <>
      <button
        type="button"
        onClick={openPanel}
        // The VISIBLE Hebrew word is the name's prefix, so WCAG 2.5.3 holds and
        // no sighted staffer sees a label she cannot verify. `min-w-11` beside
        // `min-h-11` because this control can be two characters wide.
        aria-label={count > 0 ? t("bell.labelUnread", { count }) : t("bell.label")}
        className={cn("min-h-11 min-w-11 px-2 text-sm text-ink-muted hover:text-ink", focusRing)}
      >
        {t("bell.label")}
        {count > 0 && (
          <Badge variant="neutral" aria-hidden className="ms-1">
            <bdi dir="ltr">{count > BADGE_CAP ? `${BADGE_CAP}+` : count}</bdi>
          </Badge>
        )}
      </button>

      <Modal
        open={open}
        onClose={closePanel}
        title={t("bell.title")}
        // State E: focus lands on a CONTROL, so a bare <p> is stepped over and
        // «אין התראות» would be silent. Pointing the dialog's description at it
        // is the shipped remedy for exactly this shape (GuideOverlay's).
        describedById={rendered.length === 0 && items !== null && !loadFailed ? emptyId : undefined}
        footer={
          <>
            {unreadOnPage.length > 0 && (
              <Button type="button" variant="secondary" onClick={() => void mark(unreadOnPage)}>
                {t("bell.markAll")}
              </Button>
            )}
            <Button type="button" variant="ghost" onClick={closePanel}>
              {t("bell.close")}
            </Button>
          </>
        }
      >
        {markFailed && (
          <p role="alert" className="mb-3 text-sm text-ink-muted">
            {t("bell.markFailed")}
          </p>
        )}
        {loadFailed ? (
          // F1, immediate and unconditional — the house `{ns}.loadFailed` shape,
          // `role="alert"` on the first render as on every retry.
          <div className="space-y-4">
            <p role="alert" className="text-sm text-ink-muted">
              {t("bell.loadFailed")}
            </p>
            <Button type="button" onClick={() => void load()}>
              {t("bell.retry")}
            </Button>
          </div>
        ) : items === null ? (
          <Skeleton variant="text" lines={3} />
        ) : rendered.length === 0 ? (
          <p id={emptyId} className="text-sm text-ink-muted">
            {t("bell.empty")}
          </p>
        ) : (
          <>
            <ul className="max-h-[60vh] overflow-y-auto">
              {rendered.map((row) => (
                <li key={row.id} className="border-t border-border first:border-t-0">
                  <Row row={row} onOpen={() => void openRow(row)} />
                </li>
              ))}
            </ul>
            {/* Only on a FULL page: an honest statement of the ceiling, not a
                permanent footnote. */}
            {rendered.length === 20 && (
              <p className="mt-3 text-xs text-ink-muted">{t("bell.capNote")}</p>
            )}
          </>
        )}
      </Modal>
    </>
  );
}

function Row({ row, onOpen }: { row: StaffNotification; onOpen: () => void }) {
  const { t } = useTranslation();
  const unread = row.read_at === null;
  const key = row.actor_name === null ? "bell.kindUnknownActor" : KIND_COPY[row.kind];
  const body = (
    <>
      <span className={cn("text-sm", unread ? "font-semibold text-ink" : "text-ink")}>
        {/* A BARE <bdi> on the name — `dir="ltr"` on a Hebrew name is itself a
            bug — and the interpolated node keeps the name isolated from the
            Hebrew sentence around it. */}
        {row.actor_name === null ? (
          t(key)
        ) : (
          <Interpolated template={t(key, { name: " " })} name={row.actor_name} />
        )}
      </span>
      {unread && (
        <Badge variant="neutral" className="ms-2">
          {t("bell.unreadMarker")}
        </Badge>
      )}
      {/* ABSOLUTE and Jerusalem-local, never a relative counter: F37 forbids
          live counters on this surface, and a static "3 minutes ago" that
          silently ages is worse than either. */}
      <bdi dir="ltr" className="ms-2 text-xs text-ink-muted">
        {stamp(row.created_at)}
      </bdi>
    </>
  );

  return NAVIGATES.has(row.kind) ? (
    <button type="button" onClick={onOpen} className={cn("min-h-11 w-full text-start", focusRing)}>
      {body}
    </button>
  ) : (
    <div className="min-h-11 py-2">{body}</div>
  );
}

// Today gets a time; anything older gets the date beside it. Both through the
// two shipped Jerusalem helpers — no new date code, and no `new Date()` parsing
// of a wire date anywhere.
function stamp(instant: string): string {
  const time = jerusalemTime(instant);
  return jerusalemIsoDate(instant) === todayJerusalem() ? time : `${jerusalemDate(instant)} ${time}`;
}

// Splits «{{name}} הפנתה אליך לקוחה» around the interpolated name so the name
// can sit in its own <bdi> rather than being concatenated into the sentence.
function Interpolated({ template, name }: { template: string; name: string }) {
  const [before, after] = template.split(" ");
  return (
    <>
      {before}
      <bdi>{name}</bdi>
      {after}
    </>
  );
}
