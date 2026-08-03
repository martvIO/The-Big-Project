import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Badge, Card, EmptyState, Input, Skeleton } from "@boutique/ui";
import { api } from "../api";
import type { CustomerDetailResponse, CustomerRow } from "../api";
import { customerErrorText, isolateLtr } from "../lib/booking";
import { MAX_SEARCH_TERM_LENGTH } from "../validation";
import { CustomerDetail } from "./CustomerDetail";

// Mirrors CUSTOMER_LIST_DEFAULT_LIMIT. Not parity-guarded: the server clamps the
// page itself, so a stale client can only ask for a smaller page, never a bigger
// one. There are deliberately no prev/next controls — search is the way to a
// customer past the first page, and `total` keeps the count honest either way.
const PAGE_LIMIT = 50;

// One request per pause, not one per keystroke. Six lines of setTimeout rather
// than a package or a shared hook: the debounce here has one consumer and no
// state of its own.
const SEARCH_DEBOUNCE_MS = 300;

export function CustomersSection() {
  const { t } = useTranslation();
  const [term, setTerm] = useState("");
  // null = NOT YET LOADED. Never [] on failure, which would stack an empty
  // state under the outage alert.
  const [rows, setRows] = useState<CustomerRow[] | null>(null);
  const [total, setTotal] = useState(0);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const countRef = useRef<HTMLParagraphElement | null>(null);
  // Only a RETURN from the detail moves focus — a first mount must not steal it
  // from wherever the console put it.
  const returning = useRef(false);

  useEffect(() => {
    let cancelled = false;
    const handle = setTimeout(() => {
      setRows(null);
      setLoadError(null);
      api
        .listCustomers({ q: term, offset: 0, limit: PAGE_LIMIT })
        .then((result) => {
          if (!cancelled) {
            setRows(result.items);
            setTotal(result.total);
          }
        })
        .catch((error: unknown) => {
          if (!cancelled) {
            setLoadError(customerErrorText(error, t, "customers.loadFailed"));
          }
        });
    }, SEARCH_DEBOUNCE_MS);
    return () => {
      cancelled = true;
      clearTimeout(handle);
    };
  }, [term, t]);

  // Without this, CustomerDetail unmounts with focus on its <h2> and focus goes
  // to <body>: the next Tab restarts at the skip link, WCAG 2.4.3. The
  // paragraph carries tabIndex={-1}, which is why it can receive focus at all.
  useEffect(() => {
    if (selectedId === null && returning.current) {
      returning.current = false;
      countRef.current?.focus();
    }
  }, [selectedId]);

  const loading = rows === null && loadError === null;

  if (selectedId !== null) {
    // An in-panel state swap, the BookingsSection -> BookingDetail shape:
    // apps/manage has no router and F53 does not introduce one for one view.
    return (
      <CustomerDetail
        customerId={selectedId}
        onBack={() => {
          returning.current = true;
          setSelectedId(null);
        }}
        onCustomerChanged={(next: CustomerDetailResponse) => {
          // Patched from the response, NEVER refetched: neither `name` nor
          // `phone` can move through this endpoint, so list membership and the
          // server's (name, id) order are both invariant under the only
          // mutation F53 ships. A name edit added here later WOULD need the
          // refetch, which is why this is written down.
          setRows((current) =>
            current === null
              ? current
              : current.map((customer) =>
                  customer.id === next.id ? { ...customer, tags: next.tags } : customer,
                ),
          );
        }}
      />
    );
  }

  return (
    <div className="space-y-6">
      <h2 className="text-lg font-semibold text-ink">{t("customers.heading")}</h2>

      <Card>
        <Input
          label={t("customers.searchLabel")}
          placeholder={t("customers.searchPlaceholder")}
          className="max-w-[320px]"
          // The mirrored server bound. Without it a pasted over-long term
          // answers 400 and the list renders «אפשר לנסות שוב בעוד רגע» — a
          // wait-and-retry message for an input error every retry reproduces.
          maxLength={MAX_SEARCH_TERM_LENGTH}
          // `dir` is deliberately UNSET: the term is usually Hebrew, and
          // dir="ltr" on Hebrew free text is itself a bidi defect.
          value={term}
          onChange={(event) => setTerm(event.target.value)}
        />
      </Card>

      {/* The list's single announced region: the loading state, the count and
          the post-back focus destination, all in the one place. */}
      <p
        role="status"
        tabIndex={-1}
        ref={countRef}
        data-testid="customers-count"
        className="text-sm text-ink-muted"
      >
        {loading
          ? t("customers.listLoading")
          : loadError !== null
            ? ""
            : isolateLtr(t("customers.count", { count: total }), String(total))}
      </p>

      {loadError !== null && (
        // An outage, not a fault of hers: the muted register, and no retry
        // control — editing the search box refetches.
        <p role="alert" className="text-sm text-ink-muted">
          {loadError}
        </p>
      )}

      {/* variant="text", never the default "block", which renders h-full w-full
          and collapses to zero height in a parent with no intrinsic height. */}
      {loading && <Skeleton variant="text" lines={4} />}

      {rows !== null && (
        // The Card's own p-6 is NOT overridden: cn() is a plain join, so a
        // consumer p-0 and Card's baked-in p-6 are same-specificity rules and
        // the built stylesheet emits .p-0 first — the override is silently inert.
        <Card>
          {rows.length === 0 ? (
            // TWO empty states, never one. Collapsing them would tell a boutique
            // with 200 customers that it has none.
            term.trim() === "" ? (
              <EmptyState title={t("customers.emptyTitle")} body={t("customers.emptyBody")} />
            ) : (
              <EmptyState
                title={t("customers.noResultsTitle")}
                body={t("customers.noResultsBody")}
              />
            )
          ) : (
            <ul className="divide-y divide-border">
              {rows.map((customer) => (
                <li key={customer.id}>
                  {/* One affordance per row: the whole row opens the detail.
                      py-4 + text-base clears 44px with no min-h literal. */}
                  <button
                    type="button"
                    className="flex w-full items-start gap-3 py-4 text-start"
                    onClick={() => setSelectedId(customer.id)}
                  >
                    <span className="min-w-0 grow space-y-1">
                      <span className="flex flex-wrap items-center gap-2">
                        {/* Bare bdi: dir="ltr" on a Hebrew name is itself a bidi
                            defect. */}
                        <bdi className="font-semibold text-ink">{customer.name}</bdi>
                        <bdi dir="ltr" className="text-sm text-ink-muted">
                          {customer.phone}
                        </bdi>
                      </span>
                      {customer.tags.length > 0 && (
                        // EVERY tag, no "+N" token: MAX_TAGS already bounds the
                        // set and the row wraps, so truncating would add
                        // user-visible text with no copy-deck key AND a digit
                        // run beside a `+` between Hebrew chips.
                        <span data-testid="customer-row-tags" className="flex flex-wrap gap-2">
                          {customer.tags.map((tag) => (
                            <Badge key={tag} variant="neutral">
                              <bdi>{tag}</bdi>
                            </Badge>
                          ))}
                        </span>
                      )}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
          {rows.length < total && (
            // `offset` is pinned to 0 and there is no pager, so the count in the
            // announced region above is the total under the search predicate and
            // NOT the length of this list. A boutique with 60 customers was told
            // «לקוחות ברשימה: 60» over 50 rows with nothing saying the rest
            // existed — a sentence false about the list it sits on. This is the
            // notice, not pagination: the spec defers the pager, and search is
            // the way to a customer past the first page.
            //
            // Both numbers, the customers.messagesTruncated shape one screen
            // over — mid-sentence with Hebrew on both sides, so neither run
            // needs isolating.
            <p className="pt-4 text-sm text-ink-muted">
              {t("customers.listTruncated", { count: rows.length, total })}
            </p>
          )}
        </Card>
      )}
    </div>
  );
}
