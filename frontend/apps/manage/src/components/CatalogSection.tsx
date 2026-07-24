import { useEffect, useState } from "react";
import { api, errorMessage } from "../api";
import type { Dress } from "../api";
import { formatIlsAmount, MAX_SEARCH_LENGTH } from "../validation";
import { DressEditor } from "./DressEditor";
import {
  Badge,
  cardClass,
  EmptyState,
  ErrorNotice,
  inputClass,
  labelClass,
  Loading,
  primaryButtonClass,
  secondaryButtonClass,
} from "./shared";

// Mirrors DRESS_LIST_DEFAULT_LIMIT. Not parity-guarded: the server clamps the
// page itself, so a stale client can only ask for a smaller page, never a
// bigger one.
const PAGE_SIZE = 24;
const SEARCH_DEBOUNCE_MS = 300;

// Three-way and derived client-side: without the first case a boutique that
// enters 60 dresses before filling any size matrix sees a page of "אזל מהמלאי"
// on brand-new dresses.
function stockBadge(dress: Dress) {
  if (dress.variant_count === 0) {
    return <Badge variant="muted">לא הוגדרו מידות</Badge>;
  }
  if (dress.total_quantity === 0) {
    return <Badge variant="warning">אזל מהמלאי</Badge>;
  }
  return (
    <Badge variant="muted">
      במלאי (<bdi dir="ltr">{dress.total_quantity}</bdi>)
    </Badge>
  );
}

export function CatalogSection() {
  const [dresses, setDresses] = useState<Dress[] | null>(null);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [archived, setArchived] = useState(false);
  const [search, setSearch] = useState("");
  const [appliedSearch, setAppliedSearch] = useState("");
  const [loadError, setLoadError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);

  // One request per typing pause, and the page always resets to the first.
  useEffect(() => {
    const timer = setTimeout(() => {
      setAppliedSearch(search);
      setOffset((current) => (search === appliedSearch ? current : 0));
    }, SEARCH_DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [search, appliedSearch]);

  useEffect(() => {
    let cancelled = false;
    setLoadError(null);
    api
      .listDresses({ offset, limit: PAGE_SIZE, search: appliedSearch, archived })
      .then((result) => {
        if (!cancelled) {
          setDresses(result.items);
          setTotal(result.total);
        }
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setDresses([]);
          setLoadError(errorMessage(error));
        }
      });
    return () => {
      cancelled = true;
    };
  }, [offset, appliedSearch, archived]);

  if (editing) {
    return (
      <DressEditor
        dressId={selectedId}
        onBack={() => setEditing(false)}
        // No list refetch: the derived badges and the cover can never disagree
        // between the two views if the row is patched from the mutation
        // response.
        onDressChanged={(next) => {
          setDresses((current) => {
            if (current === null) {
              return current;
            }
            return current.some((row) => row.id === next.id)
              ? current.map((row) => (row.id === next.id ? next : row))
              : [...current, next];
          });
          setSelectedId(next.id);
        }}
        onArchived={(id) => {
          setDresses((current) =>
            current === null ? current : current.filter((row) => row.id !== id),
          );
          setTotal((current) => Math.max(0, current - 1));
          setEditing(false);
        }}
      />
    );
  }

  const filtered = appliedSearch.trim() !== "" || archived;
  const firstIndex = total === 0 ? 0 : offset + 1;
  const lastIndex = Math.min(offset + PAGE_SIZE, total);

  return (
    <div className="space-y-6">
      <h2 className="text-lg font-medium">שמלות</h2>

      <section className={`${cardClass} space-y-3`}>
        <div className="flex flex-wrap items-end gap-3">
          <div className="grow">
            <label className={labelClass} htmlFor="catalog-search">
              חיפוש שמלה
            </label>
            <input
              id="catalog-search"
              className={inputClass}
              // Hebrew and Latin dress names both occur.
              dir="auto"
              maxLength={MAX_SEARCH_LENGTH}
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
          </div>
          <button
            type="button"
            className={primaryButtonClass}
            onClick={() => {
              setSelectedId(null);
              setEditing(true);
            }}
          >
            שמלה חדשה
          </button>
        </div>
        <label className="flex min-h-11 items-center gap-3 text-sm">
          <input
            type="checkbox"
            className="h-6 w-6"
            checked={archived}
            onChange={(event) => {
              setArchived(event.target.checked);
              setOffset(0);
            }}
          />
          ארכיון
        </label>
      </section>

      {/* The list screen's single polite region, and the focus destination
          after a page change. */}
      <p
        role="status"
        tabIndex={-1}
        data-testid="catalog-count"
        className="text-sm text-stone-500"
      >
        מציג <bdi dir="ltr">{firstIndex}</bdi>–<bdi dir="ltr">{lastIndex}</bdi> מתוך{" "}
        <bdi dir="ltr">{total}</bdi>
      </p>

      {loadError !== null && <ErrorNotice message={loadError} />}

      {dresses === null ? (
        <Loading />
      ) : (
        <section className={cardClass}>
          {dresses.length === 0 ? (
            archived ? (
              <EmptyState title="אין שמלות בארכיון." />
            ) : filtered ? (
              <EmptyState
                title="לא נמצאו שמלות התואמות לחיפוש."
                action={
                  <button
                    type="button"
                    className={secondaryButtonClass}
                    onClick={() => setSearch("")}
                  >
                    ניקוי החיפוש
                  </button>
                }
              />
            ) : (
              <EmptyState
                title="אין עדיין שמלות בקטלוג"
                body="השמלה הראשונה תופיע כאן ובאתר של הבוטיק."
                action={
                  <button
                    type="button"
                    className={primaryButtonClass}
                    onClick={() => {
                      setSelectedId(null);
                      setEditing(true);
                    }}
                  >
                    שמלה חדשה
                  </button>
                }
              />
            )
          ) : (
            <ul className="divide-y divide-stone-100">
              {dresses.map((row) => (
                <li key={row.id}>
                  {/* One affordance per row: the whole row opens the editor.
                      A second "עריכה" button would be two tab stops for one
                      action. */}
                  <button
                    type="button"
                    className="flex w-full items-start gap-3 py-4 text-start"
                    onClick={() => {
                      setSelectedId(row.id);
                      setEditing(true);
                    }}
                  >
                    <span className="block w-18 shrink-0 overflow-hidden rounded bg-stone-100 aspect-[3/4]">
                      {row.cover?.url != null && (
                        <img
                          src={row.cover.url}
                          // The dress name is the adjacent accessible text
                          // inside this same button.
                          alt=""
                          loading="lazy"
                          decoding="async"
                          className="h-full w-full object-cover"
                        />
                      )}
                    </span>
                    <span className="min-w-0 grow space-y-1">
                      <span className="block font-medium">{row.name}</span>
                      {/* Sibling of the name, never a child of it: a chip
                          nested in a clamped box is clipped out of the row on
                          exactly the long-name edge case. */}
                      <span className="flex flex-wrap items-center gap-2">
                        {row.reserved && <Badge>הוזמן</Badge>}
                        {row.archived && <Badge variant="muted">בארכיון</Badge>}
                        {stockBadge(row)}
                      </span>
                      <span className="flex flex-wrap items-center gap-2 text-sm text-stone-500">
                        {row.price_visible && row.price_agorot !== null ? (
                          <bdi dir="ltr">{formatIlsAmount(row.price_agorot)} ₪</bdi>
                        ) : (
                          <span className="italic">מחיר בתיאום</span>
                        )}
                        <span>
                          {row.media_count === 0 ? (
                            "אין תמונות"
                          ) : (
                            <>
                              <bdi dir="ltr">{row.media_count}</bdi> תמונות
                            </>
                          )}
                        </span>
                      </span>
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}

      <div className="flex justify-end gap-2">
        <button
          type="button"
          className={secondaryButtonClass}
          disabled={offset === 0}
          onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
        >
          הקודם
        </button>
        <button
          type="button"
          className={secondaryButtonClass}
          disabled={offset + PAGE_SIZE >= total}
          onClick={() => setOffset(offset + PAGE_SIZE)}
        >
          הבא
        </button>
      </div>
    </div>
  );
}
