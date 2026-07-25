import { useEffect, useState } from "react";
import { Badge, Button, Card, EmptyState, Input, Price, Skeleton, Toggle } from "@boutique/ui";
import { api, errorMessage } from "../api";
import type { Dress } from "../api";
import { MAX_SEARCH_LENGTH } from "../validation";
import { DressEditor } from "./DressEditor";

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
          // A create appends a row the paged count has never counted, so total
          // has to move with it — otherwise "מציג 1–1 מתוך 0" and the «הבא»
          // button both read off a count that is one behind the list.
          const isNew = dresses !== null && !dresses.some((row) => row.id === next.id);
          setDresses((current) => {
            if (current === null) {
              return current;
            }
            return current.some((row) => row.id === next.id)
              ? current.map((row) => (row.id === next.id ? next : row))
              : [...current, next];
          });
          if (isNew) {
            setTotal((current) => current + 1);
          }
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
      <h2 className="text-lg font-semibold text-ink">שמלות</h2>

      <Card className="space-y-3">
        <div className="flex flex-wrap items-end gap-3">
          <div className="grow">
            <Input
              label="חיפוש שמלה"
              // Hebrew and Latin dress names both occur.
              dir="auto"
              maxLength={MAX_SEARCH_LENGTH}
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
          </div>
          <Button
            type="button"
            onClick={() => {
              setSelectedId(null);
              setEditing(true);
            }}
          >
            שמלה חדשה
          </Button>
        </div>
        <Toggle
          label="ארכיון"
          checked={archived}
          onCheckedChange={(checked) => {
            setArchived(checked);
            setOffset(0);
          }}
        />
      </Card>

      {/* The list screen's single polite region, and the focus destination
          after a page change. */}
      <p
        role="status"
        tabIndex={-1}
        data-testid="catalog-count"
        className="text-sm text-ink-muted"
      >
        מציג <bdi dir="ltr">{firstIndex}</bdi>–<bdi dir="ltr">{lastIndex}</bdi> מתוך{" "}
        <bdi dir="ltr">{total}</bdi>
      </p>

      {loadError !== null && <p role="alert" className="text-sm text-ink-muted">{loadError}</p>}

      {dresses === null ? (
        <Skeleton variant="text" lines={4} />
      ) : (
        <Card>
          {dresses.length === 0 ? (
            archived ? (
              <EmptyState title="אין שמלות בארכיון." />
            ) : filtered ? (
              <EmptyState
                title="לא נמצאו שמלות התואמות לחיפוש."
                action={
                  <Button
                    type="button"
                    variant="secondary"
                    onClick={() => setSearch("")}
                  >
                    ניקוי החיפוש
                  </Button>
                }
              />
            ) : (
              <EmptyState
                title="אין עדיין שמלות בקטלוג"
                body="השמלה הראשונה תופיע כאן ובאתר של הבוטיק."
                action={
                  <Button
                    type="button"
                    onClick={() => {
                      setSelectedId(null);
                      setEditing(true);
                    }}
                  >
                    שמלה חדשה
                  </Button>
                }
              />
            )
          ) : (
            <ul className="divide-y divide-border">
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
                    <span className="block w-18 shrink-0 overflow-hidden rounded bg-surface aspect-[3/4]">
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
                      <span className="block font-semibold text-ink">{row.name}</span>
                      {/* Sibling of the name, never a child of it: a chip
                          nested in a clamped box is clipped out of the row on
                          exactly the long-name edge case. */}
                      <span className="flex flex-wrap items-center gap-2">
                        {row.reserved && <Badge>הוזמן</Badge>}
                        {row.archived && <Badge variant="muted">בארכיון</Badge>}
                        {stockBadge(row)}
                      </span>
                      <span className="flex flex-wrap items-center gap-2 text-sm text-ink-muted">
                        <Price
                          agorot={row.price_agorot ?? 0}
                          visible={row.price_visible && row.price_agorot !== null}
                          hiddenLabel="מחיר בתיאום"
                        />
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
        </Card>
      )}

      <div className="flex justify-end gap-2">
        <Button
          type="button"
          variant="secondary"
          disabled={offset === 0}
          onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
        >
          הקודם
        </Button>
        <Button
          type="button"
          variant="secondary"
          disabled={offset + PAGE_SIZE >= total}
          onClick={() => setOffset(offset + PAGE_SIZE)}
        >
          הבא
        </Button>
      </div>
    </div>
  );
}
