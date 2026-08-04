import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Button, Input, Modal, Select, Skeleton } from "@boutique/ui";
import { api } from "../api";
import type { AppointmentType, CustomerRow, WalkInBookingRequest } from "../api";
import { MAX_SEARCH_TERM_LENGTH } from "../validation";

/**
 * F50. The bride is at the counter and the boutique already holds her — a real
 * booking starting now, already checked in.
 *
 * ⚠ THE ABSENCES ARE THE FEATURE (D3). This dialog PICKS a customer, it never
 * creates one: the body it hands up is two ids, so nothing is obtained from the
 * subject, this is not a §11 collection point and no notice is owed. A search
 * that matches nobody is answered with a route to the check-in form at the door,
 * NOT with a name-and-phone form — that would be a fourth collection point whose
 * notice could only be delivered by asking a staffer to recite it aloud.
 *
 * The poll discipline, the {401,403} classifier and the API call all live in
 * `BoardSection`: `onConfirm` answers `null` when the parent has handled the
 * outcome (success, or a terminal that replaces the whole board) and an error
 * SENTENCE when the dialog should stay open and show it. One prop, one contract,
 * and no second classifier down here.
 */

// One request per pause, not one per keystroke — CustomersSection's six lines
// verbatim, and for the same reason: one consumer, no state of its own.
const SEARCH_DEBOUNCE_MS = 300;

// Ten, not fifty: this is a picker inside a dialog, and a staffer who has to
// scroll a list has typed too little. `total` keeps the truncation honest.
const RESULT_LIMIT = 10;

export interface WalkInDialogProps {
  open: boolean;
  onClose: () => void;
  onConfirm: (body: WalkInBookingRequest) => Promise<string | null>;
}

export function WalkInDialog({ open, onClose, onConfirm }: WalkInDialogProps) {
  const { t } = useTranslation();

  const [term, setTerm] = useState("");
  // null = NOT SEARCHED YET (a blank box), never [] — an empty array is the
  // «nobody matched» answer and the two must not render the same.
  const [results, setResults] = useState<CustomerRow[] | null>(null);
  const [total, setTotal] = useState(0);
  const [searchFailed, setSearchFailed] = useState(false);
  const [customerId, setCustomerId] = useState<string | null>(null);

  const [types, setTypes] = useState<AppointmentType[] | null>(null);
  const [typesFailed, setTypesFailed] = useState(false);
  const [typeId, setTypeId] = useState("");

  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // Every open starts clean — a customer picked and cancelled must not come
    // back on the next bride at the counter.
    if (!open) {
      return;
    }
    setTerm("");
    setResults(null);
    setTotal(0);
    setSearchFailed(false);
    setCustomerId(null);
    setTypeId("");
    setError(null);
    setBusy(false);
  }, [open]);

  useEffect(() => {
    // Once per open, not once per keystroke: the type list is small, static and
    // owner-configured.
    if (!open) {
      return;
    }
    let cancelled = false;
    setTypes(null);
    setTypesFailed(false);
    api
      .listAppointmentTypes()
      .then((rows) => {
        if (!cancelled) {
          setTypes(rows);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setTypesFailed(true);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [open]);

  useEffect(() => {
    if (!open) {
      return;
    }
    // A blank box is not a search. The server would answer «everyone», which is
    // a page of names nobody asked for on a screen with one job.
    if (term.trim() === "") {
      setResults(null);
      setTotal(0);
      setSearchFailed(false);
      return;
    }
    let cancelled = false;
    const handle = setTimeout(() => {
      setResults(null);
      setSearchFailed(false);
      api
        .listCustomers({ q: term, offset: 0, limit: RESULT_LIMIT })
        .then((page) => {
          if (!cancelled) {
            setResults(page.items);
            setTotal(page.total);
          }
        })
        .catch(() => {
          if (!cancelled) {
            setSearchFailed(true);
          }
        });
    }, SEARCH_DEBOUNCE_MS);
    return () => {
      cancelled = true;
      clearTimeout(handle);
    };
  }, [open, term]);

  const submit = async () => {
    if (customerId === null || typeId === "") {
      return;
    }
    setBusy(true);
    setError(null);
    // EXACTLY TWO KEYS. Anything else here — a note, a starts_at, a
    // marketing_consent — is a ForbidExtraModel 422 at best and a ruling
    // reversed at worst.
    const failure = await onConfirm({ customer_id: customerId, appointment_type_id: typeId });
    setBusy(false);
    if (failure !== null) {
      setError(failure);
    }
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={t("walkin.title")}
      footer={
        <>
          {/* The house pattern: ghost dismiss + secondary confirm, and the
              dismiss reuses F36's shipped «ביטול» rather than minting a second
              spelling of one word. */}
          <Button variant="ghost" size="md" fullWidthMobile={false} onClick={onClose}>
            {t("rooms.cancel")}
          </Button>
          <Button
            variant="secondary"
            size="md"
            fullWidthMobile={false}
            loading={busy}
            disabled={customerId === null || typeId === ""}
            onClick={() => void submit()}
          >
            {t("walkin.confirm")}
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <Input
          label={t("walkin.searchLabel")}
          help={t("walkin.searchHelp")}
          className="min-h-11"
          // The mirrored server bound, for the reason CustomersSection carries
          // it: a pasted over-long term otherwise answers 400 and the dialog
          // shows a wait-and-retry sentence for an input error every retry
          // reproduces.
          maxLength={MAX_SEARCH_TERM_LENGTH}
          // `dir` deliberately UNSET: the term is usually a Hebrew name, and
          // dir="ltr" on Hebrew free text is itself a bidi defect.
          value={term}
          onChange={(event) => {
            setTerm(event.target.value);
            // A customer chosen out of the previous result set is not a customer
            // in this one.
            setCustomerId(null);
          }}
        />

        {searchFailed ? (
          <p role="alert" className="text-sm text-danger">
            {t("walkin.searchFailed")}
          </p>
        ) : term.trim() !== "" && results === null ? (
          <Skeleton variant="text" lines={3} />
        ) : results !== null && results.length === 0 ? (
          // ⚠ NOT role="alert" and not an error colour. This is the ordinary
          // answer to a search that matched nothing, and the sentence is D3's
          // ruling as product copy: her route in is the form at the door.
          <p data-testid="walkin-empty" className="text-sm text-ink">
            {t("walkin.empty")}
          </p>
        ) : results !== null ? (
          <fieldset className="space-y-2">
            <legend className="text-sm font-semibold text-ink">{t("walkin.resultsLegend")}</legend>
            {results.map((customer) => (
              <label key={customer.id} className="flex min-h-11 items-center gap-3 text-base">
                <input
                  type="radio"
                  name="walkin-customer"
                  value={customer.id}
                  checked={customerId === customer.id}
                  onChange={() => setCustomerId(customer.id)}
                />
                {/* Bare bdi on the name — dir="ltr" would reverse the visual
                    order of «נועה לוי»'s words. The phone IS forced LTR: it is a
                    numeric run, and it ships at all because it is the
                    disambiguator two brides with one name need. */}
                <bdi className="text-ink">{customer.name}</bdi>
                <bdi dir="ltr" className="text-ink-muted">
                  {customer.phone}
                </bdi>
              </label>
            ))}
            {total > results.length && (
              // Stated, never absorbed — the board's own rule, and it bites
              // hardest here: two brides with one name, one of them off screen.
              <p className="text-sm text-ink-muted">
                {t("walkin.truncated", { count: results.length })}
              </p>
            )}
          </fieldset>
        ) : null}

        {typesFailed ? (
          <p role="alert" className="text-sm text-danger">
            {t("walkin.typesFailed")}
          </p>
        ) : types === null ? (
          <Skeleton variant="text" lines={1} />
        ) : types.length === 0 ? (
          <p className="text-sm text-ink">{t("walkin.typesEmpty")}</p>
        ) : (
          <Select
            label={t("walkin.typeLabel")}
            className="min-h-11"
            value={typeId}
            onChange={(event) => setTypeId(event.target.value)}
          >
            <option value="">{t("walkin.typePlaceholder")}</option>
            {types.map((type) => (
              <option key={type.id} value={type.id}>
                {type.name}
              </option>
            ))}
          </Select>
        )}

        {/* This dialog IS the confirm: the consequence sits directly above the
            one submit rather than stacking a second focus trap over a decision
            she is already reading. */}
        <p className="text-sm text-ink">{t("walkin.consequence")}</p>

        {error !== null && (
          // The dialog stays OPEN — closing it would throw away the search she
          // would have to run again.
          <p role="alert" className="text-sm text-danger">
            {error}
          </p>
        )}
      </div>
    </Modal>
  );
}
