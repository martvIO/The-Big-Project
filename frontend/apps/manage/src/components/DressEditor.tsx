import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import { api, ApiError, errorMessage } from "../api";
import type { Dress, DressDetail, DressInput } from "../api";
import {
  agorotFromIlsInput,
  ilsFromAgorot,
  MAX_DRESS_DESCRIPTION_LENGTH,
  MAX_DRESS_NAME_LENGTH,
  MAX_SORT_ORDER,
  validateDress,
} from "../validation";
import { MediaGallery } from "./MediaGallery";
import { Badge, Button, Card, Input, Modal, Price, Skeleton, TextArea, Toggle } from "@boutique/ui";
import { VariantMatrix } from "./VariantMatrix";

// The Card-level explanation, and the short form that each disabled control
// carries on its own visible label.
const CREATE_HINT = "יש לשמור את השמלה לפני הוספת מידות ותמונות";
const CREATE_REASON = "יש לשמור את השמלה תחילה";
const ARCHIVED_HINT = "השמלה בארכיון — לשחזור לחצי «שחזור».";
const ARCHIVED_REASON = "השמלה בארכיון";

// Archive and restore are both predicated UPDATEs, so a 404 from either means
// the work is already done — never an error the owner needs to read.
function isAlreadyDone(error: unknown): boolean {
  return error instanceof ApiError && error.status === 404;
}

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
  const archiveTriggerRef = useRef<HTMLButtonElement | null>(null);
  const wasConfirming = useRef(false);

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

  // The archive trigger unmounts while its confirm modal is open, so native
  // focus-return lands on <body>. Restore focus to the trigger on close.
  useEffect(() => {
    if (wasConfirming.current && !confirmingArchive) {
      archiveTriggerRef.current?.focus();
    }
    wasConfirming.current = confirmingArchive;
  }, [confirmingArchive]);

  const creating = dressId === null && detail === null;
  const archived = detail?.archived === true;

  if (dressId !== null && detail === null) {
    return loadError !== null ? (
      <p role="alert" className="text-sm text-ink-muted">
        {loadError}
      </p>
    ) : (
      <Skeleton variant="text" lines={4} />
    );
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
      // Archive is predicated on `deleted_at IS NULL`, so a 404 means somebody
      // already archived it in another tab. That is the outcome she asked for —
      // converge on it instead of surfacing the API's English "Resource not
      // found." in an otherwise fully-Hebrew console.
      if (isAlreadyDone(error)) {
        onArchived(detail.id);
        return;
      }
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
      // Symmetrically: restore is predicated on `deleted_at IS NOT NULL`, so a
      // 404 means it is already restored. Re-read rather than trust the local
      // copy — the other tab may have changed more than the archive flag.
      if (isAlreadyDone(error)) {
        try {
          applyDetail(await api.getDress(detail.id));
          return;
        } catch (refetchError) {
          setFormError(errorMessage(refetchError));
          return;
        }
      }
      setFormError(errorMessage(error));
    }
  };

  const priceAgorot =
    draft.priceIls.trim() === "" ? null : agorotFromIlsInput(draft.priceIls);
  const priceShown = draft.priceVisible && priceAgorot !== null && priceAgorot > 0;

  return (
    <div className="space-y-6">
      <Button variant="secondary" onClick={onBack}>
        חזרה לרשימת השמלות
      </Button>

      <div className="flex flex-wrap items-center gap-3">
        <h2 ref={heading} tabIndex={-1} className="text-lg font-semibold">
          {detail === null ? "שמלה חדשה" : detail.name}
        </h2>
        {archived && <Badge variant="muted">בארכיון</Badge>}
        {detail?.reserved === true && <Badge>הוזמן</Badge>}
      </div>

      {archived && <p className="text-sm text-ink-muted">{ARCHIVED_HINT}</p>}

      <Card>
        <form onSubmit={(event) => void handleSubmit(event)} className="space-y-4">
          <h3 className="text-sm font-semibold">פרטי השמלה</h3>
          <p className="text-xs text-ink-muted">שדות המסומנים ב-* הם חובה</p>

          <div>
            <Input
              label="שם השמלה *"
              dir="auto"
              required
              maxLength={MAX_DRESS_NAME_LENGTH}
              value={draft.name}
              disabled={saving || archived}
              onChange={(event) => setDraft({ ...draft, name: event.target.value })}
            />
            <p className="mt-1 text-xs text-ink-muted">
              <bdi dir="ltr">
                {draft.name.length}/{MAX_DRESS_NAME_LENGTH}
              </bdi>
            </p>
          </div>

          <div>
            <TextArea
              label="תיאור"
              className="min-h-30"
              dir="auto"
              maxLength={MAX_DRESS_DESCRIPTION_LENGTH}
              value={draft.description}
              disabled={saving || archived}
              onChange={(event) => setDraft({ ...draft, description: event.target.value })}
            />
            <p className="mt-1 text-xs text-ink-muted">
              <bdi dir="ltr">
                {draft.description.length}/{MAX_DRESS_DESCRIPTION_LENGTH}
              </bdi>
            </p>
          </div>

          {/* An LTR island: the box keeps its RTL position, only its content
              direction flips. The ₪ lives in the label, never in the field. */}
          <Input
            label="מחיר (₪)"
            inputMode="decimal"
            dir="ltr"
            className="max-w-40"
            value={draft.priceIls}
            disabled={saving || archived}
            onChange={(event) => setDraft({ ...draft, priceIls: event.target.value })}
          />

          <Toggle
            label="הצגת המחיר באתר"
            description="כשהאפשרות כבויה, הלקוחות רואות «מחיר בתיאום» במקום הסכום."
            checked={draft.priceVisible}
            disabled={saving || archived}
            onCheckedChange={(checked) => setDraft({ ...draft, priceVisible: checked })}
          />

          {/* The single place price and visibility resolve to one readable
              outcome, so neither field can be misunderstood alone. */}
          <p className="border-s-4 border-warning-text bg-surface-raised p-3 text-sm">
            <span className="text-ink-muted">בקטלוג יוצג: </span>
            <Price agorot={priceAgorot ?? 0} visible={priceShown} hiddenLabel="מחיר בתיאום" />
          </p>

          <Toggle
            label="הוזמן"
            description="סימון ידני, ללא תאריך — יש להסיר ידנית כשהשמלה מתפנה"
            checked={draft.reserved}
            disabled={saving || archived}
            onCheckedChange={(checked) => setDraft({ ...draft, reserved: checked })}
          />

          <div>
            <Input
              label="סדר בקטלוג"
              type="number"
              dir="ltr"
              className="max-w-24"
              min={-MAX_SORT_ORDER}
              max={MAX_SORT_ORDER}
              value={draft.sortOrder}
              disabled={saving || archived}
              onChange={(event) => setDraft({ ...draft, sortOrder: event.target.value })}
            />
            <p className="mt-1 text-xs text-ink-muted">מספר נמוך = מוצג ראשון</p>
          </div>

          {formError !== null && (
            <p role="alert" className="text-sm text-danger">
              {formError}
            </p>
          )}

          <div className="flex items-center justify-end gap-3">
            {savedCue !== null && (
              <span role="status" className="text-xs text-ink-muted">
                {savedCue}
              </span>
            )}
            <Button type="submit" loading={saving} disabled={archived}>
              {detail === null ? "יצירת שמלה" : "שמירה"}
            </Button>
          </div>
        </form>
      </Card>

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
        <div className="border-t border-border pt-4">
          {archived ? (
            <Button variant="secondary" onClick={() => void handleRestore()}>
              שחזור
            </Button>
          ) : (
            <>
              {/* The trigger and the modal's confirm share the name "העברה
                  לארכיון", so only one may be in the tree at a time — the trigger
                  unmounts while the modal is open. Native focus-return then lands
                  on <body>, so a focus-restore effect below sends it back to the
                  trigger on close. */}
              {!confirmingArchive && (
                <Button ref={archiveTriggerRef} variant="danger" onClick={() => setConfirmingArchive(true)}>
                  העברה לארכיון
                </Button>
              )}
              <Modal
                open={confirmingArchive}
                onClose={() => setConfirmingArchive(false)}
                title={`להעביר את «${detail.name}» לארכיון?`}
                footer={
                  <>
                    <Button variant="ghost" onClick={() => setConfirmingArchive(false)}>
                      ביטול
                    </Button>
                    <Button variant="danger" onClick={() => void handleArchive()}>
                      העברה לארכיון
                    </Button>
                  </>
                }
              >
                השמלה תוסר מהאתר. אפשר לשחזר אותה מלשונית «ארכיון».
              </Modal>
            </>
          )}
        </div>
      )}
    </div>
  );
}
