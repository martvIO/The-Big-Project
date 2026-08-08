import { useCallback, useEffect, useRef, useState } from "react";
import {
  Button,
  Card,
  DateField,
  EmptyState,
  Input,
  Modal,
  Skeleton,
  TextArea,
  formatDateRange,
} from "@boutique/ui";
import type { FormattedDateRange } from "@boutique/ui";
import { api, ApiError, errorMessage } from "../api";
import type { CustomerRow, Reservation } from "../api";

// Q9's cleaning-and-return gap, and the ONLY place the number lives. A tenant
// setting is the recorded upgrade if a boutique ever wants a different default;
// until one asks, a named constant beats a settings row nobody edits.
export const RESERVATION_BUFFER_DAYS = 5;
// Mirrors MAX_RESERVATION_NOTES_LENGTH / MAX_RESERVATION_SPAN_DAYS in
// backend/app/catalog/validation.py. Client-side bounds are a courtesy; the
// server refuses independently.
const MAX_NOTES_LENGTH = 500;
const MAX_SPAN_DAYS = 365;
const CUSTOMER_RESULT_LIMIT = 5;

const HEADING = "הזמנות לתאריך";
const EXPLAINER =
  "בתאריכים האלה השמלה מוצגת באתר כלא זמינה, ומדידות בתאריכים אחרים נקבעות כרגיל.";
const WEDDING_LABEL = "תאריך החתונה";
const WEDDING_HELP =
  "הטווח מתמלא אוטומטית — יום החתונה ועוד חמישה ימים לניקוי ולהחזרה. אפשר לערוך את התאריכים.";
const START_LABEL = "מהתאריך";
// The inclusivity is stated on the LABEL, not in a help line: it is the one
// thing an owner can get wrong by a whole day, and D2 made it a schema decision.
const END_LABEL = "עד התאריך (כולל)";
const CUSTOMER_LABEL = "לקוחה (לא חובה) — חיפוש לפי שם או טלפון";
const NOTES_LABEL = "הערות";
const NOTES_HELP = "לקוחה שאינה במערכת אפשר לרשום כאן.";
const ADD_LABEL = "הוספת הזמנה";
const EMPTY_TITLE = "אין הזמנות לשמלה הזאת.";
const EMPTY_BODY = "הוסיפי הזמנה בטופס למטה.";
const ADDED_CUE = "ההזמנה נוספה.";
const DELETED_CUE = "ההזמנה נמחקה.";
const DELETE_LABEL = "מחיקה";
const DELETE_TITLE = "למחוק את ההזמנה?";
const DELETE_BODY =
  "מחיקת ההזמנה מפנה את התאריכים באתר מיד, גם אם ההשכרה עדיין פעילה.";
const LOAD_ERROR = "לא הצלחנו לטעון את ההזמנות כרגע.";
// Its own state, never the load error and never the empty state: an archived
// dress may well have reservations, they are simply unreadable until restore.
const ARCHIVED_LIST = "רשימת ההזמנות מוצגת אחרי שחזור השמלה מהארכיון.";
const RETRY_LABEL = "ניסיון נוסף";
const ORDER_ERROR = "תאריך הסיום לפני תאריך ההתחלה";
const SPAN_ERROR = "טווח ההזמנה ארוך משנה";
const REMOVE_CUSTOMER = "הסרה";
const LOADING_CUE = "טוענת את ההזמנות";

// ⚠ DATE PARTS, NEVER MILLISECONDS. `new Date(ms + 5 * 86400000)` is off by an
// hour across a DST boundary and can land on the previous day; Date's UTC
// setters do exact calendar arithmetic and month/year/leap rollover for free.
function addDays(dateOnly: string, days: number): string {
  const date = new Date(`${dateOnly}T00:00:00Z`);
  if (Number.isNaN(date.getTime())) {
    return "";
  }
  date.setUTCDate(date.getUTCDate() + days);
  return date.toISOString().slice(0, 10);
}

function daysBetween(startsOn: string, endsOn: string): number {
  const start = new Date(`${startsOn}T00:00:00Z`).getTime();
  const end = new Date(`${endsOn}T00:00:00Z`).getTime();
  return Math.round((end - start) / 86_400_000);
}

// One numeral run gets one island; two whole dates get one each, with the dash
// in RTL flow between them (R19's split shape).
function RangeText({ range }: { range: FormattedDateRange }) {
  if (range.kind === "same-month") {
    return (
      <>
        <bdi dir="ltr">{range.days}</bdi> {range.month}
      </>
    );
  }
  return (
    <>
      <bdi dir="ltr">{range.start}</bdi> – <bdi dir="ltr">{range.end}</bdi>
    </>
  );
}

function rangeToText(range: FormattedDateRange): string {
  return range.kind === "same-month"
    ? `${range.days} ${range.month}`
    : `${range.start} – ${range.end}`;
}

export interface ReservationsPaneProps {
  dressId: string | null;
  disabled: boolean;
  // Short enough to append to a control's own visible label.
  disabledReason: string | null;
  // The Card-level explanation, a real <p> so AT reads it even though every
  // control inside is `disabled`.
  disabledHint?: string | null;
}

export function ReservationsPane({
  dressId,
  disabled,
  disabledReason,
  disabledHint = null,
}: ReservationsPaneProps) {
  const [rows, setRows] = useState<Reservation[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadFailed, setLoadFailed] = useState(false);
  const [wedding, setWedding] = useState("");
  const [startsOn, setStartsOn] = useState("");
  const [endsOn, setEndsOn] = useState("");
  // The prefill is a convenience, not a source of truth: once she edits either
  // range field, a later wedding-date change must not silently undo her work.
  const [rangeTouched, setRangeTouched] = useState(false);
  const [notes, setNotes] = useState("");
  const [customer, setCustomer] = useState<CustomerRow | null>(null);
  const [customerQuery, setCustomerQuery] = useState("");
  const [customerResults, setCustomerResults] = useState<CustomerRow[]>([]);
  const [formError, setFormError] = useState<string | null>(null);
  const [endError, setEndError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [cue, setCue] = useState<string | null>(null);
  const [confirmingId, setConfirmingId] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);
  // The post-mutation focus destination — the shipped console pattern
  // (BookingsSection, CatalogSection). Needed here because the delete trigger
  // unmounts with its row, so the modal's native focus return lands on <body>.
  const listRegion = useRef<HTMLParagraphElement>(null);

  // Archived is the only way this pane arrives disabled WITH a dress id —
  // create mode has no id yet — and GET …/reservations 404s on an archived
  // dress by construction (DressesRepository.by_id pins deleted_at IS NULL).
  // Fetching would paint a permanent red alert, over a retry that can never
  // succeed, on a state that is not an error.
  const archived = disabled && dressId !== null;

  const reload = useCallback(async () => {
    if (dressId === null || archived) {
      return;
    }
    setLoading(true);
    try {
      const response = await api.listDressReservations(dressId);
      setRows(response.items);
      setLoadFailed(false);
    } catch {
      setLoadFailed(true);
      setRows([]);
    } finally {
      setLoading(false);
    }
  }, [dressId, archived]);

  useEffect(() => {
    void reload();
  }, [reload]);

  useEffect(() => {
    if (customer !== null || customerQuery.trim() === "" || dressId === null) {
      setCustomerResults([]);
      return;
    }
    let live = true;
    void (async () => {
      try {
        const response = await api.listCustomers({
          q: customerQuery,
          offset: 0,
          limit: CUSTOMER_RESULT_LIMIT,
        });
        if (live) {
          setCustomerResults(response.items);
        }
      } catch {
        if (live) {
          setCustomerResults([]);
        }
      }
    })();
    return () => {
      live = false;
    };
  }, [customerQuery, customer, dressId]);

  const applyWedding = (value: string) => {
    setWedding(value);
    if (rangeTouched || value === "") {
      return;
    }
    setStartsOn(value);
    setEndsOn(addDays(value, RESERVATION_BUFFER_DAYS));
  };

  const handleAdd = async () => {
    if (dressId === null) {
      return;
    }
    setCue(null);
    setEndError(null);
    setFormError(null);
    if (startsOn === "" || endsOn === "") {
      setFormError(ORDER_ERROR);
      return;
    }
    const span = daysBetween(startsOn, endsOn);
    if (span < 0) {
      setEndError(ORDER_ERROR);
      return;
    }
    if (span > MAX_SPAN_DAYS) {
      setFormError(SPAN_ERROR);
      return;
    }
    setSaving(true);
    try {
      await api.createDressReservation(dressId, {
        starts_on: startsOn,
        ends_on: endsOn,
        customer_id: customer?.id ?? null,
        notes: notes.trim() === "" ? null : notes.trim(),
      });
      setWedding("");
      setStartsOn("");
      setEndsOn("");
      setRangeTouched(false);
      setNotes("");
      setCustomer(null);
      setCustomerQuery("");
      setCue(ADDED_CUE);
      await reload();
    } catch (error) {
      // The 409 names WHICH dates collide — that is the whole reason the body
      // carries `details`, and re-rendering it as prose is what saves her a
      // trip to the list to work it out.
      if (error instanceof ApiError && error.code === "RESERVATION_OVERLAP") {
        const conflict = error.details;
        const range =
          conflict?.starts_on !== undefined && conflict.ends_on !== undefined
            ? rangeToText(formatDateRange(conflict.starts_on, conflict.ends_on))
            : "";
        setFormError(
          range === ""
            ? "התאריכים מתנגשים עם הזמנה קיימת. אפשר לבחור תאריכים אחרים."
            : `התאריכים מתנגשים עם הזמנה קיימת (${range}). אפשר לבחור תאריכים אחרים.`,
        );
      } else {
        setFormError(errorMessage(error));
      }
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (reservationId: string) => {
    if (dressId === null) {
      return;
    }
    setDeleting(true);
    try {
      await api.deleteDressReservation(dressId, reservationId);
      setConfirmingId(null);
      setCue(DELETED_CUE);
      await reload();
      listRegion.current?.focus();
    } catch (error) {
      setConfirmingId(null);
      setFormError(errorMessage(error));
    } finally {
      setDeleting(false);
    }
  };

  const suffix = disabledReason === null ? "" : ` (${disabledReason})`;

  return (
    <Card className="space-y-4">
      <h3 className="text-sm font-semibold text-ink">{HEADING}</h3>
      <p className="text-sm text-ink-muted">{EXPLAINER}</p>
      {/* Full contrast, never behind an opacity veil: this paragraph is the one
          thing explaining the state, and WCAG's inactive-control exemption does
          not cover it. */}
      {disabledHint !== null && disabledHint !== undefined && (
        <p className="text-sm text-ink-muted">{disabledHint}</p>
      )}

      <p ref={listRegion} role="status" tabIndex={-1} className="text-sm text-ink-muted">
        {cue}
      </p>

      {archived ? (
        <p className="text-sm text-ink-muted">{ARCHIVED_LIST}</p>
      ) : loadFailed ? (
        <div className="space-y-2">
          <p role="alert" className="text-sm text-danger">
            {LOAD_ERROR}
          </p>
          <Button variant="secondary" onClick={() => void reload()}>
            {RETRY_LABEL}
          </Button>
        </div>
      ) : loading ? (
        <>
          <span className="sr-only">{LOADING_CUE}</span>
          <Skeleton />
        </>
      ) : rows.length === 0 ? (
        <EmptyState title={EMPTY_TITLE} body={EMPTY_BODY} />
      ) : (
        <ul className="divide-y divide-border">
          {rows.map((row) => (
            <li key={row.id} className="flex flex-wrap items-center gap-3 py-3 text-sm">
              <span className="font-semibold text-ink">
                <RangeText range={formatDateRange(row.starts_on, row.ends_on)} />
              </span>
              {row.customer_name !== null && (
                <span className="text-ink-muted">{row.customer_name}</span>
              )}
              {row.notes !== null && (
                <span dir="auto" className="text-ink-muted">
                  {row.notes}
                </span>
              )}
              <Button
                variant="danger"
                className="ms-auto"
                disabled={disabled}
                aria-label={`${DELETE_LABEL} — ${rangeToText(
                  formatDateRange(row.starts_on, row.ends_on),
                )}`}
                onClick={() => setConfirmingId(row.id)}
              >
                {DELETE_LABEL}
              </Button>
            </li>
          ))}
        </ul>
      )}

      <div className="space-y-3 border-t border-border pt-4">
        <DateField
          label={`${WEDDING_LABEL}${suffix}`}
          help={WEDDING_HELP}
          value={wedding}
          disabled={disabled}
          onChange={(event) => applyWedding(event.target.value)}
        />
        <div className="flex flex-wrap gap-3">
          <div className="grow">
            <DateField
              label={START_LABEL}
              value={startsOn}
              disabled={disabled}
              onChange={(event) => {
                setRangeTouched(true);
                setStartsOn(event.target.value);
              }}
            />
          </div>
          <div className="grow">
            <DateField
              label={END_LABEL}
              value={endsOn}
              error={endError ?? undefined}
              disabled={disabled}
              onChange={(event) => {
                setRangeTouched(true);
                setEndsOn(event.target.value);
              }}
            />
          </div>
        </div>

        {customer === null ? (
          <div className="space-y-2">
            <Input
              label={CUSTOMER_LABEL}
              dir="auto"
              value={customerQuery}
              disabled={disabled}
              onChange={(event) => setCustomerQuery(event.target.value)}
            />
            {customerResults.length > 0 && (
              // A filtered list of real buttons, each its own tab stop — no
              // combobox ARIA to get wrong, and nothing to announce that the
              // list itself does not already say.
              <ul className="space-y-1">
                {customerResults.map((row) => (
                  <li key={row.id}>
                    <Button variant="ghost" onClick={() => setCustomer(row)}>
                      {row.name} <bdi dir="ltr">{row.phone}</bdi>
                    </Button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        ) : (
          <div className="flex flex-wrap items-center gap-2 text-sm">
            <span className="text-ink">{customer.name}</span>
            <Button variant="ghost" disabled={disabled} onClick={() => setCustomer(null)}>
              {REMOVE_CUSTOMER}
            </Button>
          </div>
        )}

        <TextArea
          label={NOTES_LABEL}
          help={NOTES_HELP}
          dir="auto"
          maxLength={MAX_NOTES_LENGTH}
          value={notes}
          disabled={disabled}
          onChange={(event) => setNotes(event.target.value)}
        />

        {formError !== null && (
          <p role="alert" className="text-sm text-danger">
            {formError}
          </p>
        )}

        <div className="flex justify-end">
          <Button loading={saving} disabled={disabled} onClick={() => void handleAdd()}>
            {`${ADD_LABEL}${suffix}`}
          </Button>
        </div>
      </div>

      <Modal
        open={confirmingId !== null}
        onClose={() => setConfirmingId(null)}
        title={DELETE_TITLE}
        footer={
          <>
            <Button variant="ghost" onClick={() => setConfirmingId(null)}>
              ביטול
            </Button>
            <Button
              variant="danger"
              loading={deleting}
              onClick={() => {
                if (confirmingId !== null) {
                  void handleDelete(confirmingId);
                }
              }}
            >
              {DELETE_LABEL}
            </Button>
          </>
        }
      >
        {DELETE_BODY}
      </Modal>
    </Card>
  );
}
