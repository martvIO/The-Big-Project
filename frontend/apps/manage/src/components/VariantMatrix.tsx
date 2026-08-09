import { useEffect, useRef, useState } from "react";
import { Badge, Button, Card, EmptyState, Input } from "@boutique/ui";
import { api, errorMessage } from "../api";
import type { DressDetail, Variant, VariantInput } from "../api";
import {
  EU_SIZE_QUICK_LIST,
  MAX_SIZE_LABEL_LENGTH,
  MAX_VARIANT_QUANTITY,
  MAX_VARIANTS_PER_DRESS,
  normalizeSizeLabel,
  sizeKey,
  validateVariants,
} from "../validation";

interface Row {
  // Stable across re-renders and reorders; a saved row reuses its server id.
  key: string;
  size_label: string;
  quantity: string;
}

export interface VariantMatrixProps {
  dressId: string | null;
  variants: Variant[];
  disabled: boolean;
  // Short enough to append to a control's own visible label.
  disabledReason: string | null;
  // The Card-level explanation, a real <p> so AT reads it even though every
  // control inside is `disabled`.
  disabledHint?: string | null;
  onDetail: (detail: DressDetail) => void;
}

function rowsFromVariants(variants: Variant[]): Row[] {
  return variants.map((variant) => ({
    key: variant.id,
    size_label: variant.size_label,
    quantity: String(variant.quantity),
  }));
}

function toInputs(rows: Row[]): VariantInput[] {
  return rows.map((row, index) => ({
    size_label: normalizeSizeLabel(row.size_label),
    quantity: Number(row.quantity) || 0,
    sort_order: index,
  }));
}

function totalQuantity(rows: Row[]): number {
  return rows.reduce((sum, row) => sum + (Number(row.quantity) || 0), 0);
}

function sameAsLoaded(rows: Row[], variants: Variant[]): boolean {
  if (rows.length !== variants.length) {
    return false;
  }
  return rows.every(
    (row, index) =>
      normalizeSizeLabel(row.size_label) === variants[index].size_label &&
      (Number(row.quantity) || 0) === variants[index].quantity,
  );
}

export function VariantMatrix({
  dressId,
  variants,
  disabled,
  disabledReason,
  disabledHint = null,
  onDetail,
}: VariantMatrixProps) {
  const [rows, setRows] = useState<Row[]>(() => rowsFromVariants(variants));
  const [custom, setCustom] = useState("");
  const [inlineError, setInlineError] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const nextKey = useRef(0);
  const loaded = useRef(variants);

  // The server response is the authority after every save; reload the draft
  // whenever the parent hands down a different set.
  useEffect(() => {
    if (loaded.current !== variants) {
      loaded.current = variants;
      setRows(rowsFromVariants(variants));
      setInlineError(null);
    }
  }, [variants]);

  const listed = new Set(rows.map((row) => sizeKey(row.size_label)));
  const atCap = rows.length >= MAX_VARIANTS_PER_DRESS;
  const total = totalQuantity(rows);
  const allZero = rows.length > 0 && total === 0;
  const dirty = !sameAsLoaded(rows, variants);

  // Every disabled control states its reason on its OWN visible label: disabled
  // drops it from the tab order, so a detached paragraph is never read.
  const capReason = atCap ? `הגעת ל-${MAX_VARIANTS_PER_DRESS} מידות` : null;
  const blockedReason = disabled ? disabledReason : capReason;
  const suffix = blockedReason === null ? "" : ` — ${blockedReason}`;
  const addBlocked = disabled || atCap;

  const addSize = (label: string) => {
    const normalized = normalizeSizeLabel(label);
    if (!normalized) {
      return;
    }
    if (rows.length >= MAX_VARIANTS_PER_DRESS) {
      setInlineError(`אפשר עד ${MAX_VARIANTS_PER_DRESS} מידות לשמלה.`);
      return;
    }
    if (listed.has(sizeKey(normalized))) {
      setInlineError(`המידה «${normalized}» כבר קיימת ברשימה.`);
      return;
    }
    nextKey.current += 1;
    setRows([...rows, { key: `new-${nextKey.current}`, size_label: normalized, quantity: "0" }]);
    setInlineError(null);
    setCustom("");
  };

  const handleSave = async () => {
    if (dressId === null) {
      return;
    }
    const inputs = toInputs(rows);
    const invalid = validateVariants(inputs);
    if (invalid !== null) {
      setInlineError(invalid);
      return;
    }
    setSaving(true);
    try {
      const detail = await api.replaceVariants(dressId, inputs);
      onDetail(detail);
      setInlineError(null);
      setSaveError(null);
    } catch (error) {
      setSaveError(errorMessage(error));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Card className="space-y-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="text-sm font-semibold text-ink">מידות ומלאי</h3>
        <p className="text-sm text-ink-muted">
          סה״כ במלאי: <bdi dir="ltr">{total}</bdi> יחידות
        </p>
      </div>

      {/* Full contrast, never behind an opacity veil: this paragraph is the one
          thing explaining the state, and WCAG's inactive-control exemption does
          not cover it. */}
      {disabledHint !== null && <p className="text-sm text-ink-muted">{disabledHint}</p>}

      <div role="group" aria-labelledby="variant-quick-label" className="space-y-2">
        <p id="variant-quick-label" className="text-sm font-semibold text-ink">
          {`הוספה מהירה (מידות אירופאיות)${suffix}`}
        </p>
        <div className="flex flex-wrap gap-2">
          {EU_SIZE_QUICK_LIST.map((size) => {
            const label = String(size);
            const alreadyListed = listed.has(sizeKey(label));
            return (
              <button
                key={size}
                type="button"
                // Not aria-pressed: a second press does not un-press, it moves
                // focus to the existing row. The state lives in the name.
                aria-label={alreadyListed ? `${label} — כבר ברשימה` : undefined}
                className={`min-h-11 min-w-11 rounded-full border px-3 text-sm ${
                  alreadyListed
                    ? // ⚠ text-ink, NOT text-gold-strong. tokens.md bars
                      // --color-gold-strong from carrying text or a
                      // meaning-bearing glyph: it is a NON-TEXT colour that
                      // clears only the ≥3:1 bar, and gold-strong on
                      // surface-raised measures 3.93:1 against the 4.5 text
                      // floor. The selected affordance stays gold where the
                      // token allows it — the border, and the aria-hidden
                      // bullet below, which tokens.md exempts as decorative
                      // because visible text always sits beside it.
                      "border-gold-strong bg-surface-raised font-semibold text-ink"
                    : "border-border text-ink-muted"
                } disabled:opacity-50`}
                disabled={addBlocked}
                onClick={() => addSize(label)}
              >
                <bdi dir="ltr">{label}</bdi>
                {alreadyListed && (
                  // A real element, never ::before{content} — generated content
                  // is folded into the accessible name in Chrome and Firefox.
                  <span aria-hidden="true" className="ms-1 text-gold-strong">
                    •
                  </span>
                )}
              </button>
            );
          })}
        </div>
      </div>

      <div className="flex flex-wrap items-end gap-2">
        <div className="grow">
          <Input
            label={`מידה מותאמת${blockedReason === null ? "" : ` (${blockedReason})`}`}
            // Both "מידה מיוחדת" and "US 6 / EU 36" occur.
            dir="auto"
            maxLength={MAX_SIZE_LABEL_LENGTH}
            value={custom}
            disabled={addBlocked}
            onChange={(event) => setCustom(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                event.preventDefault();
                addSize(custom);
              }
            }}
          />
        </div>
        <Button
          variant="secondary"
          disabled={addBlocked}
          aria-label={capReason === null ? undefined : `הוספה — ${capReason}`}
          onClick={() => addSize(custom)}
        >
          הוספה
        </Button>
      </div>

      {inlineError !== null && (
        <p role="alert" className="text-xs text-danger">
          {inlineError}
        </p>
      )}
      {saveError !== null && (
        <p role="alert" className="text-sm text-danger">
          {saveError}
        </p>
      )}

      {rows.length === 0 ? (
        <EmptyState
          title="לא הוגדרו מידות לשמלה הזו."
          body="בחרי מידה מהרשימה המהירה, או הוסיפי מידה מותאמת."
        />
      ) : (
        <ul className="divide-y divide-border">
          {rows.map((row, index) => {
            const label = normalizeSizeLabel(row.size_label);
            const quantity = Number(row.quantity) || 0;
            return (
              <li key={row.key} className="flex flex-wrap items-center gap-3 py-3 text-sm">
                <Badge variant="muted" id={`variant-size-${row.key}`}>
                  <bdi>{label}</bdi>
                </Badge>
                <span id={`variant-qty-label-${row.key}`} className="text-ink-muted">
                  כמות
                </span>
                {/* LTR island: − value + reads left-to-right while "כמות" stays
                    in the RTL flow outside it. */}
                <span dir="ltr" className="flex items-center gap-1" style={{ unicodeBidi: "isolate" }}>
                  <Button
                    variant="secondary"
                    className="min-w-11"
                    aria-label={`הפחתת כמות במידה ${label}`}
                    disabled={disabled || saving || quantity === 0}
                    onClick={() =>
                      setRows(
                        rows.map((current, position) =>
                          position === index
                            ? { ...current, quantity: String(Math.max(0, quantity - 1)) }
                            : current,
                        ),
                      )
                    }
                  >
                    −
                  </Button>
                  <input
                    type="number"
                    dir="ltr"
                    min={0}
                    max={MAX_VARIANT_QUANTITY}
                    // Numeric column: value sits at the end (right in this LTR island).
                    className="w-24 rounded-sm border border-border-input bg-surface-raised px-3 py-2 text-base text-ink text-end focus:border-gold-strong focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
                    // aria-labelledby, not aria-label: an aria-label would
                    // silently replace the visible "כמות" text.
                    aria-labelledby={`variant-qty-label-${row.key} variant-size-${row.key}`}
                    value={row.quantity}
                    disabled={disabled || saving}
                    onChange={(event) =>
                      setRows(
                        rows.map((current, position) =>
                          position === index
                            ? { ...current, quantity: event.target.value }
                            : current,
                        ),
                      )
                    }
                  />
                  <Button
                    variant="secondary"
                    className="min-w-11"
                    aria-label={`הגדלת כמות במידה ${label}`}
                    disabled={disabled || saving || quantity >= MAX_VARIANT_QUANTITY}
                    onClick={() =>
                      setRows(
                        rows.map((current, position) =>
                          position === index
                            ? { ...current, quantity: String(quantity + 1) }
                            : current,
                        ),
                      )
                    }
                  >
                    +
                  </Button>
                </span>
                <Button
                  variant="danger"
                  className="ms-auto min-h-11"
                  // The accessible name BEGINS with the visible label verbatim.
                  aria-label={`הסרה — מידה ${label}`}
                  disabled={disabled || saving}
                  onClick={() => {
                    setRows(rows.filter((_, position) => position !== index));
                    setInlineError(null);
                  }}
                >
                  הסרה
                </Button>
              </li>
            );
          })}
        </ul>
      )}

      {allZero && (
        <p role="status" className="text-sm text-warning-text">
          כל המידות במלאי 0 — השמלה תסומן «אזל מהמלאי» בקטלוג הניהול.
        </p>
      )}

      <div className="flex items-center justify-end gap-3">
        {dirty && !disabled && <span className="text-xs text-warning-text">יש שינויים שלא נשמרו</span>}
        <Button
          disabled={disabled || saving || dressId === null}
          onClick={() => void handleSave()}
        >
          שמירת מלאי
        </Button>
      </div>
    </Card>
  );
}
