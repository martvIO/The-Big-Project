import { useEffect, useRef, useState } from "react";
import type { ChangeEvent } from "react";
import { Button, Card, EmptyState, Input, Modal } from "@boutique/ui";
import { api, ApiError, errorMessage, uploadToStorage } from "../api";
import type { DressDetail, Media } from "../api";
import { MAX_MEDIA_PER_DRESS, validateUploadFile } from "../validation";

type QueueState = "pending" | "uploading" | "verifying" | "done" | "failed";

interface QueueItem {
  key: string;
  name: string;
  size: number;
  state: QueueState;
  reason: string | null;
  // A client-side rejection is never retriable: the same file fails identically.
  retriable: boolean;
  file: File | null;
  // Survives a transient storage 5xx at confirm: the object is already in the
  // bucket and its row is still pending, so the retry re-confirms this id
  // instead of re-posting 9 MB over cellular. Null everywhere else, because
  // every other failure path deletes the row it minted.
  mediaId: string | null;
}

export interface MediaGalleryProps {
  dressId: string | null;
  dressName: string;
  media: Media[];
  uploadsEnabled: boolean;
  slotsRemaining: number;
  disabled: boolean;
  disabledReason: string | null;
  disabledHint?: string | null;
  onDetail: (detail: DressDetail) => void;
}

function formatBytes(bytes: number): string {
  if (bytes >= 1_000_000) {
    return `${(bytes / 1_000_000).toFixed(1)}MB`;
  }
  return `${Math.max(1, Math.round(bytes / 1000))}KB`;
}

// The failure the owner reads, never an S3 XML body or an AWS string.
function uploadFailureMessage(error: unknown): string {
  if (error instanceof ApiError) {
    switch (error.code) {
      case "MEDIA_MISMATCH":
        return "הקובץ אינו תמונה תקינה.";
      case "MEDIA_NOT_UPLOADED":
        return "הקובץ לא הגיע לשרת. נסי שוב.";
      case "MEDIA_LIMIT_REACHED":
        return "הגלריה מלאה. ייתכן שהעלאות שנכשלו עדיין תופסות מקום — רענני את העמוד ונסי שוב.";
      case "TOO_MANY_ATTEMPTS":
        return "יותר מדי העלאות בזמן קצר. נסי שוב בעוד כמה דקות.";
      case "MEDIA_NOT_CONFIGURED":
      case "MEDIA_STORAGE_UNAVAILABLE":
        return "אחסון התמונות אינו זמין כרגע. התמונות שכבר הועלו מוצגות כרגיל.";
      default:
        return error.message;
    }
  }
  return errorMessage(error);
}

export function MediaGallery({
  dressId,
  dressName,
  media,
  uploadsEnabled,
  slotsRemaining,
  disabled,
  disabledReason,
  disabledHint = null,
  onDetail,
}: MediaGalleryProps) {
  const [queue, setQueue] = useState<QueueItem[]>([]);
  const [batchAlert, setBatchAlert] = useState<string | null>(null);
  const [announcement, setAnnouncement] = useState("");
  const [storageNotice, setStorageNotice] = useState<string | null>(null);
  const [optimistic, setOptimistic] = useState<Media[] | null>(null);
  const [confirmingDeleteId, setConfirmingDeleteId] = useState<string | null>(null);
  const [failedImages, setFailedImages] = useState<string[]>([]);

  // Focus follows the photo, not the index: the index has just changed under it.
  const buttonRefs = useRef(new Map<string, HTMLButtonElement | null>());
  const pendingFocus = useRef<string | null>(null);
  // Exactly one detail refetch per gallery mount, however many signed URLs
  // expire at once.
  const hasRefreshed = useRef(false);
  const nextKey = useRef(0);

  const items = optimistic ?? media;
  const lastMedia = useRef(media);

  // The optimistic order stands until the authoritative list arrives from the
  // parent — clearing it on the response instead would flash the old order.
  useEffect(() => {
    if (lastMedia.current !== media) {
      lastMedia.current = media;
      setOptimistic(null);
    }
  }, [media]);

  useEffect(() => {
    const key = pendingFocus.current;
    if (key === null) {
      return;
    }
    const target = buttonRefs.current.get(key);
    if (target !== null && target !== undefined && !target.disabled) {
      target.focus();
      pendingFocus.current = null;
    }
  });

  const uploadsBlocked = disabled || !uploadsEnabled || dressId === null;
  const inputReason = disabled
    ? disabledReason
    : uploadsEnabled
      ? null
      : "לא זמין כרגע";
  const inputLabel = `הוספת תמונות${inputReason === null ? "" : ` (${inputReason})`}`;

  const setItem = (key: string, patch: Partial<QueueItem>) => {
    setQueue((current) =>
      current.map((item) => (item.key === key ? { ...item, ...patch } : item)),
    );
  };

  const runOne = async (item: QueueItem): Promise<boolean> => {
    if (dressId === null || (item.file === null && item.mediaId === null)) {
      return false;
    }
    setItem(item.key, { state: "uploading", reason: null });
    // Non-null only on a retry after a transient storage 5xx at confirm: the
    // object is already up, so presign and POST are skipped entirely.
    let mediaId: string | null = item.mediaId;
    try {
      if (mediaId === null) {
        if (item.file === null) {
          return false;
        }
        const presign = await api.presignMedia(dressId, {
          content_type: item.file.type,
          byte_size: item.file.size,
        });
        mediaId = presign.media_id;
        setItem(item.key, { mediaId });
        await uploadToStorage(presign, item.file);
      }
      setItem(item.key, { state: "verifying" });
      const detail = await api.confirmMedia(dressId, mediaId);
      onDetail(detail);
      setItem(item.key, { state: "done", reason: null, file: null, mediaId: null });
      return true;
    } catch (error) {
      // MEDIA_STORAGE_UNAVAILABLE is the one failure the server promises left
      // the pending row untouched and still confirmable. Deleting it here would
      // destroy the only recovery state there is and force a full re-upload of
      // an object that already reached the bucket.
      const transient =
        error instanceof ApiError && error.code === "MEDIA_STORAGE_UNAVAILABLE";
      if (mediaId !== null && !transient) {
        // Release the pending row so the gallery slot is freed immediately —
        // this is why media DELETE accepts a pending row.
        try {
          await api.deleteMedia(dressId, mediaId);
        } catch {
          // The row expires on its own after an hour; nothing to show here.
        }
        mediaId = null;
      }
      setItem(item.key, {
        state: "failed",
        reason: uploadFailureMessage(error),
        retriable: true,
        mediaId,
      });
      if (error instanceof ApiError && error.status === 503) {
        setStorageNotice(uploadFailureMessage(error));
      }
      return false;
    }
  };

  const runQueue = async (batch: QueueItem[], alreadyFailed: number) => {
    let uploaded = 0;
    for (let index = 0; index < batch.length; index += 1) {
      setAnnouncement(`מעלה ${index + 1} מתוך ${batch.length}`);
      // Sequential on the wire on purpose: one non-terminal row at a time is
      // what makes the queue itself a legible progress affordance.
      if (await runOne(batch[index])) {
        uploaded += 1;
      }
    }
    const failed = batch.length - uploaded + alreadyFailed;
    if (batch.length === 1 && failed === 0) {
      setAnnouncement(`התמונה נוספה. ${media.length + 1} מתוך ${MAX_MEDIA_PER_DRESS}`);
    } else {
      // Terminal, on the SAME region — a summary that stops at the last
      // "מעלה…" leaves every failure silent.
      setAnnouncement(
        `הועלו ${uploaded} מתוך ${batch.length}${failed > 0 ? ` · ${failed} נכשלו` : ""}`,
      );
    }
  };

  const handleFiles = async (event: ChangeEvent<HTMLInputElement>) => {
    const selected = Array.from(event.target.files ?? []);
    event.target.value = "";
    if (selected.length === 0) {
      return;
    }
    const rows: QueueItem[] = [];
    const accepted: QueueItem[] = [];
    let rejected = 0;
    for (const file of selected) {
      nextKey.current += 1;
      let reason = validateUploadFile(file);
      if (reason === null && accepted.length >= slotsRemaining) {
        reason = `ניתן להעלות עד ${MAX_MEDIA_PER_DRESS} תמונות לשמלה — נותרו ${slotsRemaining}`;
      }
      const row: QueueItem = {
        key: `q${nextKey.current}`,
        name: file.name,
        size: file.size,
        state: reason === null ? "pending" : "failed",
        reason,
        retriable: false,
        file: reason === null ? file : null,
        mediaId: null,
      };
      rows.push(row);
      if (reason === null) {
        accepted.push(row);
      } else {
        rejected += 1;
      }
    }
    setQueue(rows);
    // The one failure with no request and no focus move, so it must be
    // assertive: focus is still standing in the file input.
    setBatchAlert(rejected > 0 ? `${rejected} קבצים לא צורפו — פרטים ברשימה למטה` : null);
    if (accepted.length > 0) {
      await runQueue(accepted, rejected);
    } else {
      setAnnouncement(`הועלו 0 מתוך 0 · ${rejected} נכשלו`);
    }
  };

  const handleRetry = async (key: string) => {
    const item = queue.find((row) => row.key === key);
    if (item === undefined || (item.file === null && item.mediaId === null)) {
      return;
    }
    // A retry that has to re-upload always takes a FRESH presign — the previous
    // policy dies with its 5-minute TTL. The one exception is a pending row that
    // survived a transient storage 5xx, where runOne re-confirms its id.
    await runQueue([item], 0);
  };

  const applyOrder = async (order: Media[], focusKey: string, message: string) => {
    if (dressId === null) {
      return;
    }
    setOptimistic(order);
    pendingFocus.current = focusKey;
    setAnnouncement(message);
    try {
      const detail = await api.reorderMedia(
        dressId,
        order.map((row) => row.id),
      );
      onDetail(detail);
    } catch (error) {
      setOptimistic(null);
      if (error instanceof ApiError && error.code === "MEDIA_ORDER_MISMATCH" && dressId !== null) {
        const detail = await api.getDress(dressId);
        onDetail(detail);
        setAnnouncement("הסדר עודכן מחדש");
      } else {
        setAnnouncement(errorMessage(error));
      }
    }
  };

  const move = (index: number, delta: number) => {
    const target = index + delta;
    if (target < 0 || target >= items.length) {
      return;
    }
    const order = [...items];
    const [moved] = order.splice(index, 1);
    order.splice(target, 0, moved);
    // If the button just used is now disabled (the photo reached an end),
    // focus its sibling rather than letting focus drop to <body>.
    const atEnd = target === 0 || target === order.length - 1;
    const wanted = delta < 0 ? "up" : "down";
    const sibling = wanted === "up" ? "down" : "up";
    const focusKey = `${moved.id}:${atEnd ? sibling : wanted}`;
    void applyOrder(order, focusKey, `התמונה הועברה למקום ${target + 1} מתוך ${order.length}`);
  };

  const makePrimary = (index: number) => {
    const order = [...items];
    const [moved] = order.splice(index, 1);
    order.unshift(moved);
    // Its ↑ is now disabled and its set-primary action no longer exists, so
    // focus cannot stay on the control that was activated.
    void applyOrder(order, `${moved.id}:delete`, `התמונה הועברה למקום 1 מתוך ${order.length}`);
  };

  const handleDelete = async (mediaId: string) => {
    if (dressId === null) {
      return;
    }
    setConfirmingDeleteId(null);
    try {
      const detail = await api.deleteMedia(dressId, mediaId);
      onDetail(detail);
      setAnnouncement("התמונה נמחקה");
    } catch (error) {
      setAnnouncement(errorMessage(error));
    }
  };

  // @boutique/ui Button is a plain function component whose props type carries no
  // `ref`, so the reorder focus map is populated from a display:contents wrapper
  // that reaches the real <button> — the effect still focuses a DOM button.
  const registerButton = (key: string) => (node: HTMLSpanElement | null) => {
    buttonRefs.current.set(key, node?.querySelector("button") ?? null);
  };

  const handleImageError = (mediaId: string) => {
    setFailedImages((current) =>
      current.includes(mediaId) ? current : [...current, mediaId],
    );
    if (hasRefreshed.current || dressId === null) {
      return;
    }
    hasRefreshed.current = true;
    api
      .getDress(dressId)
      .then(onDetail)
      .catch(() => {
        // A failed refresh leaves the placeholder tiles standing; retrying
        // would just re-request expired URLs.
      });
  };

  return (
    <Card className="space-y-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="text-sm font-semibold">תמונות</h3>
        <p className={media.length >= MAX_MEDIA_PER_DRESS ? "text-sm text-warning-text" : "text-sm text-ink-muted"}>
          {media.length >= MAX_MEDIA_PER_DRESS ? (
            "הגלריה מלאה"
          ) : (
            <>
              <bdi dir="ltr">{media.length}</bdi> מתוך <bdi dir="ltr">{MAX_MEDIA_PER_DRESS}</bdi>
            </>
          )}
        </p>
      </div>

      {disabledHint !== null && <p className="text-sm text-ink-muted">{disabledHint}</p>}

      {/* Exactly one polite region in this Card (the assertive batch-rejection
          alert below is the only other one): the storage notice, the reorder
          result and the queue summary — running AND terminal — share it. */}
      <div role="status" className="space-y-2">
        {(!uploadsEnabled || storageNotice !== null) && (
          <div className="rounded border border-border bg-surface px-3 py-2 text-sm">
            {storageNotice !== null ? (
              <p>{storageNotice}</p>
            ) : (
              <>
                <p className="font-medium">העלאת תמונות עדיין לא זמינה</p>
                <p className="text-ink-muted">
                  אפשר להמשיך למלא את פרטי השמלה ואת המידות — התמונות יתווספו מאוחר יותר.
                </p>
              </>
            )}
          </div>
        )}
        <p className="text-xs text-ink-muted">{announcement}</p>
      </div>

      {/* A real, visible, focusable file input — display:none plus a label shim
          breaks Safari/VoiceOver and hides the disabled reason. */}
      <Input
        label={inputLabel}
        help="צלמי לאורך (פורטרט). עד 10MB לתמונה · JPG/PNG/WebP · 4–6 תמונות לשמלה מספיקות"
        type="file"
        multiple
        accept="image/jpeg,image/png,image/webp"
        disabled={uploadsBlocked}
        onChange={(event) => void handleFiles(event)}
      />

      {batchAlert !== null && (
        <p role="alert" className="text-xs text-danger">
          {batchAlert}
        </p>
      )}

      {queue.length > 0 && (
        <ul className="divide-y divide-border text-sm">
          {queue.map((item) => (
            <li key={item.key} className="flex flex-wrap items-center gap-3 py-2">
              <span dir="auto" className="font-medium">
                {item.name}
              </span>
              <bdi dir="ltr" className="text-ink-muted">
                {formatBytes(item.size)}
              </bdi>
              <span className={item.state === "failed" ? "text-danger" : "text-ink-muted"}>
                {item.state === "pending" && "ממתין"}
                {item.state === "uploading" && "מעלה…"}
                {item.state === "verifying" && "מאמת…"}
                {item.state === "done" && "הועלתה"}
                {item.state === "failed" && (
                  <>
                    {"נכשלה — "}
                    <span>{item.reason}</span>
                  </>
                )}
              </span>
              {item.state === "failed" && item.retriable && (
                <Button
                  variant="secondary"
                  aria-label={`נסי שוב — ${item.name}`}
                  onClick={() => void handleRetry(item.key)}
                >
                  נסי שוב
                </Button>
              )}
            </li>
          ))}
        </ul>
      )}

      {items.length === 0 ? (
        <EmptyState
          title="אין עדיין תמונות לשמלה הזו."
          body="התמונה הראשונה תהיה התמונה הראשית בקטלוג."
        />
      ) : (
        <ol className="grid grid-cols-2 gap-4 sm:grid-cols-3">
          {items.map((item, index) => (
            <li key={item.id} className="space-y-2">
              <div className="relative aspect-[3/4] overflow-hidden rounded-md bg-surface shadow-sm">
                <span className="absolute top-1 start-1 rounded-full bg-surface-raised px-2 text-xs">
                  <bdi dir="ltr">{index + 1}</bdi>
                </span>
                {item.url !== null && !failedImages.includes(item.id) ? (
                  <img
                    src={item.url}
                    alt={`${dressName} — תמונה ${index + 1}`}
                    loading="lazy"
                    decoding="async"
                    className="h-full w-full object-cover"
                    onError={() => handleImageError(item.id)}
                  />
                ) : (
                  <span aria-hidden="true" className="flex h-full w-full items-center justify-center text-ink-muted">
                    ✦
                  </span>
                )}
              </div>
              {index === 0 ? (
                <p className="text-xs font-semibold text-warning-text">תמונה ראשית (מוצגת בקטלוג)</p>
              ) : (
                <Button
                  variant="secondary"
                  aria-label={`קבעי כתמונה ראשית — תמונה ${index + 1}`}
                  disabled={disabled}
                  onClick={() => makePrimary(index)}
                >
                  קבעי כתמונה ראשית
                </Button>
              )}
              <div className="flex flex-wrap items-center gap-1">
                {/* ↑/↓ rather than ←/→: reorder is a list-position operation and
                    the arrows must not invert in RTL. */}
                <span style={{ display: "contents" }} ref={registerButton(`${item.id}:up`)}>
                  <Button
                    variant="secondary"
                    className="min-w-11"
                    aria-label={`הזזת תמונה ${index + 1} אחורה`}
                    disabled={disabled || index === 0}
                    onClick={() => move(index, -1)}
                  >
                    <span aria-hidden="true">↑</span>
                  </Button>
                </span>
                <span style={{ display: "contents" }} ref={registerButton(`${item.id}:down`)}>
                  <Button
                    variant="secondary"
                    className="min-w-11"
                    aria-label={`הזזת תמונה ${index + 1} קדימה`}
                    disabled={disabled || index === items.length - 1}
                    onClick={() => move(index, 1)}
                  >
                    <span aria-hidden="true">↓</span>
                  </Button>
                </span>
                <span style={{ display: "contents" }} ref={registerButton(`${item.id}:delete`)}>
                  <Button
                    variant="danger"
                    aria-label={`מחיקה — תמונה ${index + 1}`}
                    disabled={disabled}
                    onClick={() => setConfirmingDeleteId(item.id)}
                  >
                    מחיקה
                  </Button>
                </span>
              </div>
            </li>
          ))}
        </ol>
      )}

      <Modal
        open={confirmingDeleteId !== null}
        onClose={() => setConfirmingDeleteId(null)}
        title="למחוק את התמונה?"
        footer={
          <>
            <Button variant="ghost" onClick={() => setConfirmingDeleteId(null)}>
              ביטול
            </Button>
            <Button
              variant="danger"
              onClick={() => {
                if (confirmingDeleteId !== null) {
                  void handleDelete(confirmingDeleteId);
                }
              }}
            >
              מחיקה
            </Button>
          </>
        }
      >
        לא ניתן לשחזר תמונה שנמחקה.
      </Modal>
    </Card>
  );
}
