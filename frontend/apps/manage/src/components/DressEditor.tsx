import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import { api, errorMessage } from "../api";
import type { Dress, DressDetail, DressInput } from "../api";
import {
  agorotFromIlsInput,
  formatIlsAmount,
  ilsFromAgorot,
  MAX_DRESS_DESCRIPTION_LENGTH,
  MAX_DRESS_NAME_LENGTH,
  MAX_SORT_ORDER,
  validateDress,
} from "../validation";
import { MediaGallery } from "./MediaGallery";
import {
  Badge,
  cardClass,
  dangerButtonClass,
  ErrorNotice,
  inputClass,
  labelClass,
  Loading,
  primaryButtonClass,
  secondaryButtonClass,
} from "./shared";
import { VariantMatrix } from "./VariantMatrix";

// The Card-level explanation, and the short form that each disabled control
// carries on its own visible label.
const CREATE_HINT = "יש לשמור את השמלה לפני הוספת מידות ותמונות";
const CREATE_REASON = "יש לשמור את השמלה תחילה";
const ARCHIVED_HINT = "השמלה בארכיון — לשחזור לחצי «שחזור».";
const ARCHIVED_REASON = "השמלה בארכיון";

interface DressDraft {
  name: string;
  description: string;
  priceIls: string;
  priceVisible: boolean;
  reserved: boolean;
  sortOrder: string;
}

const emptyDraft: DressDraft = {
  name: "",
  description: "",
  priceIls: "",
  priceVisible: true,
  reserved: false,
  sortOrder: "0",
};

function draftFromDress(dress: Dress): DressDraft {
  return {
    name: dress.name,
    description: dress.description ?? "",
    priceIls: dress.price_agorot === null ? "" : ilsFromAgorot(dress.price_agorot),
    priceVisible: dress.price_visible,
    reserved: dress.reserved,
    sortOrder: String(dress.sort_order),
  };
}

// The owner types ILS; money travels as integer agorot.
function toInput(draft: DressDraft): DressInput | string {
  let priceAgorot: number | null = null;
  if (draft.priceIls.trim() !== "") {
    priceAgorot = agorotFromIlsInput(draft.priceIls);
    if (priceAgorot === null) {
      return "המחיר אינו תקין (שקלים, עד שתי ספרות אחרי הנקודה)";
    }
  }
  const input: DressInput = {
    name: draft.name.trim(),
    description: draft.description.trim() === "" ? null : draft.description,
    price_agorot: priceAgorot === 0 ? null : priceAgorot,
    price_visible: draft.priceVisible,
    reserved: draft.reserved,
    sort_order: Number(draft.sortOrder) || 0,
  };
  const invalid = validateDress({
    name: input.name,
    description: input.description,
    price_agorot: input.price_agorot,
    sort_order: input.sort_order,
  });
  return invalid ?? input;
}

export interface DressEditorProps {
  dressId: string | null;
  onBack: () => void;
  onDressChanged: (dress: Dress) => void;
  onArchived: (dressId: string) => void;
}

export function DressEditor({ dressId, onBack, onDressChanged, onArchived }: DressEditorProps) {
  const [detail, setDetail] = useState<DressDetail | null>(null);
  const [draft, setDraft] = useState<DressDraft>(emptyDraft);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [savedCue, setSavedCue] = useState<string | null>(null);
  const [confirmingArchive, setConfirmingArchive] = useState(false);
  const heading = useRef<HTMLHeadingElement | null>(null);

  useEffect(() => {
    if (dressId === null) {
      return;
    }
    let cancelled = false;
    api
      .getDress(dressId)
      .then((loaded) => {
        if (!cancelled) {
          setDetail(loaded);
          setDraft(draftFromDress(loaded));
        }
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setLoadError(errorMessage(error));
        }
      });
    return () => {
      cancelled = true;
    };
  }, [dressId]);

  // The owner hears where she landed when a row opens the editor.
  useEffect(() => {
    heading.current?.focus();
  }, [detail?.id]);

  const creating = dressId === null && detail === null;
  const archived = detail?.archived === true;

  if (dressId !== null && detail === null) {
    return loadError !== null ? <ErrorNotice message={loadError} /> : <Loading />;
  }

  const applyDetail = (next: DressDetail) => {
    setDetail(next);
    setDraft(draftFromDress(next));
    onDressChanged(next);
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const input = toInput(draft);
    if (typeof input === "string") {
      setFormError(input);
      return;
    }
    setSaving(true);
    try {
      if (detail === null) {
        const created = await api.createDress(input);
        onDressChanged(created);
        // Load the detail and switch to edit mode in place, so
        // media_uploads_enabled is always known before a file input exists.
        const loaded = await api.getDress(created.id);
        setDetail(loaded);
        setDraft(draftFromDress(loaded));
        setSavedCue("השמלה נוצרה. אפשר להוסיף מידות ותמונות.");
      } else {
        const updated = await api.updateDress(detail.id, input);
        // PATCH answers with the dress, not the detail — keep the loaded
        // variants and media rather than dropping them.
        setDetail({ ...detail, ...updated });
        onDressChanged(updated);
        setSavedCue("נשמר לפני רגע");
      }
      setFormError(null);
    } catch (error) {
      setFormError(errorMessage(error));
    } finally {
      setSaving(false);
    }
  };

  const handleArchive = async () => {
    if (detail === null) {
      return;
    }
    setConfirmingArchive(false);
    try {
      await api.archiveDress(detail.id);
      onArchived(detail.id);
    } catch (error) {
      // A 404 means somebody already archived it — treat it as done.
      setFormError(errorMessage(error));
    }
  };

  const handleRestore = async () => {
    if (detail === null) {
      return;
    }
    try {
      applyDetail(await api.restoreDress(detail.id));
    } catch (error) {
      setFormError(errorMessage(error));
    }
  };

  const priceAgorot =
    draft.priceIls.trim() === "" ? null : agorotFromIlsInput(draft.priceIls);
  const previewPrice =
    draft.priceVisible && priceAgorot !== null && priceAgorot > 0
      ? `${formatIlsAmount(priceAgorot)} ₪`
      : null;

  return (
    <div className="space-y-6">
      <button type="button" className={secondaryButtonClass} onClick={onBack}>
        חזרה לרשימת השמלות
      </button>

      <div className="flex flex-wrap items-center gap-3">
        <h2 ref={heading} tabIndex={-1} className="text-lg font-medium">
          {detail === null ? "שמלה חדשה" : detail.name}
        </h2>
        {archived && <Badge variant="muted">בארכיון</Badge>}
        {detail?.reserved === true && <Badge>הוזמן</Badge>}
      </div>

      {archived && <p className="text-sm text-stone-600">{ARCHIVED_HINT}</p>}

      <form onSubmit={(event) => void handleSubmit(event)} className={`${cardClass} space-y-4`}>
        <h3 className="text-sm font-semibold">פרטי השמלה</h3>
        <p className="text-xs text-stone-500">שדות המסומנים ב-* הם חובה</p>

        <div>
          <label className={labelClass} htmlFor="dress-name">
            שם השמלה *
          </label>
          <input
            id="dress-name"
            className={inputClass}
            dir="auto"
            required
            maxLength={MAX_DRESS_NAME_LENGTH}
            value={draft.name}
            disabled={saving || archived}
            onChange={(event) => setDraft({ ...draft, name: event.target.value })}
          />
          <p className="mt-1 text-xs text-stone-500">
            <bdi dir="ltr">
              {draft.name.length}/{MAX_DRESS_NAME_LENGTH}
            </bdi>
          </p>
        </div>

        <div>
          <label className={labelClass} htmlFor="dress-description">
            תיאור
          </label>
          <textarea
            id="dress-description"
            className={`${inputClass} min-h-30`}
            dir="auto"
            maxLength={MAX_DRESS_DESCRIPTION_LENGTH}
            value={draft.description}
            disabled={saving || archived}
            onChange={(event) => setDraft({ ...draft, description: event.target.value })}
          />
          <p className="mt-1 text-xs text-stone-500">
            <bdi dir="ltr">
              {draft.description.length}/{MAX_DRESS_DESCRIPTION_LENGTH}
            </bdi>
          </p>
        </div>

        <div>
          <label className={labelClass} htmlFor="dress-price">
            מחיר (₪)
          </label>
          {/* An LTR island: the box keeps its RTL position, only its content
              direction flips. The ₪ lives in the label, never in the field. */}
          <input
            id="dress-price"
            inputMode="decimal"
            dir="ltr"
            className={`${inputClass} max-w-40`}
            value={draft.priceIls}
            disabled={saving || archived}
            onChange={(event) => setDraft({ ...draft, priceIls: event.target.value })}
          />
        </div>

        <label className="flex min-h-11 items-center gap-3 text-sm">
          <input
            type="checkbox"
            className="h-6 w-6"
            checked={draft.priceVisible}
            disabled={saving || archived}
            onChange={(event) => setDraft({ ...draft, priceVisible: event.target.checked })}
          />
          הצגת המחיר באתר
        </label>
        <p className="ps-9 text-xs text-stone-500">
          כשהאפשרות כבויה, הלקוחות רואות «מחיר בתיאום» במקום הסכום.
        </p>

        {/* The single place price and visibility resolve to one readable
            outcome, so neither field can be misunderstood alone. */}
        <p className="border-s-4 border-amber-400 bg-white p-3 text-sm">
          <span className="text-stone-500">בקטלוג יוצג: </span>
          {previewPrice === null ? (
            <span className="italic text-stone-500">מחיר בתיאום</span>
          ) : (
            <bdi dir="ltr">{previewPrice}</bdi>
          )}
        </p>

        <label className="flex min-h-11 items-center gap-3 text-sm">
          <input
            type="checkbox"
            className="h-6 w-6"
            checked={draft.reserved}
            disabled={saving || archived}
            onChange={(event) => setDraft({ ...draft, reserved: event.target.checked })}
          />
          הוזמן
        </label>
        <p className="ps-9 text-xs text-stone-500">
          סימון ידני, ללא תאריך — יש להסיר ידנית כשהשמלה מתפנה
        </p>

        <div>
          <label className={labelClass} htmlFor="dress-sort">
            סדר בקטלוג
          </label>
          <input
            id="dress-sort"
            type="number"
            dir="ltr"
            className={`${inputClass} max-w-24`}
            min={-MAX_SORT_ORDER}
            max={MAX_SORT_ORDER}
            value={draft.sortOrder}
            disabled={saving || archived}
            onChange={(event) => setDraft({ ...draft, sortOrder: event.target.value })}
          />
          <p className="mt-1 text-xs text-stone-500">מספר נמוך = מוצג ראשון</p>
        </div>

        {formError !== null && <ErrorNotice message={formError} />}

        <div className="flex items-center justify-end gap-3">
          {savedCue !== null && (
            <span role="status" className="text-xs text-stone-500">
              {savedCue}
            </span>
          )}
          <button type="submit" className={primaryButtonClass} disabled={saving || archived}>
            {detail === null ? "יצירת שמלה" : "שמירה"}
          </button>
        </div>
      </form>

      <VariantMatrix
        dressId={detail?.id ?? null}
        variants={detail?.variants ?? []}
        disabled={creating || archived}
        disabledReason={creating ? CREATE_REASON : archived ? ARCHIVED_REASON : null}
        disabledHint={creating ? CREATE_HINT : null}
        onDetail={applyDetail}
      />

      <MediaGallery
        dressId={detail?.id ?? null}
        dressName={detail?.name ?? ""}
        media={detail?.media ?? []}
        uploadsEnabled={detail?.media_uploads_enabled ?? true}
        slotsRemaining={detail?.media_slots_remaining ?? 0}
        disabled={creating || archived}
        disabledReason={creating ? CREATE_REASON : archived ? ARCHIVED_REASON : null}
        disabledHint={creating ? CREATE_HINT : null}
        onDetail={applyDetail}
      />

      {detail !== null && (
        <div className="border-t border-stone-200 pt-4">
          {archived ? (
            <button
              type="button"
              className={secondaryButtonClass}
              onClick={() => void handleRestore()}
            >
              שחזור
            </button>
          ) : confirmingArchive ? (
            <div className="space-y-2 rounded border border-red-300 p-3 text-sm">
              <p className="font-medium">להעביר את «{detail.name}» לארכיון?</p>
              <p className="text-stone-600">
                השמלה תוסר מהאתר. אפשר לשחזר אותה מלשונית «ארכיון».
              </p>
              <div className="flex gap-2">
                <button
                  type="button"
                  className={secondaryButtonClass}
                  onClick={() => setConfirmingArchive(false)}
                >
                  ביטול
                </button>
                <button
                  type="button"
                  className={dangerButtonClass}
                  onClick={() => void handleArchive()}
                >
                  העברה לארכיון
                </button>
              </div>
            </div>
          ) : (
            <button
              type="button"
              className={dangerButtonClass}
              onClick={() => setConfirmingArchive(true)}
            >
              העברה לארכיון
            </button>
          )}
        </div>
      )}
    </div>
  );
}
