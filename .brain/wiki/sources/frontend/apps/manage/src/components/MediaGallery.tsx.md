---
tags: [frontend, manage, react, media, uploads, accessibility, hardcoded-hebrew, f8]
sources: [frontend/apps/manage/src/components/MediaGallery.tsx]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/apps/manage/src/components/MediaGallery.tsx
blob: b0dbcb236f71d50af1cc97e2244367c8c668cd8d
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# frontend/apps/manage/src/components/MediaGallery.tsx

**Role.** The dress photo panel: a sequential presign → PUT → confirm upload queue with per-file states and a retry that knows *which* half to retry, plus keyboard reordering, set-primary, delete-with-confirm, and an expired-signed-URL self-heal. It is the most failure-path-dense component in the console, and almost all of its complexity is recovery rather than happy path.

**Module.** [[frontend/apps/manage/src/components/_index]] · **Layer.** ui

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `MediaGallery` | component | see props below |
| `MediaGalleryProps` | interface | `{ dressId: string \| null; dressName: string; media: Media[]; uploadsEnabled: boolean; slotsRemaining: number; disabled: boolean; disabledReason: string \| null; disabledHint?: string \| null; onDetail: (detail: DressDetail) => void }` |
| `QueueItem` / `QueueState` | type (module-private) | `pending \| uploading \| verifying \| done \| failed`, plus `retriable`, the `File`, and a possible `mediaId` |
| `uploadFailureMessage` | fn (module-private) | Maps six `ApiError` codes to Hebrew; everything else falls through |
| `formatBytes` | fn (module-private) | `MB`/`KB`, floored at 1KB |

## Behavior

**The upload is three calls and the failure handling turns on which one broke.** `runOne` presigns, PUTs to storage, then confirms — and on failure normally deletes the pending row it minted, which is exactly why the media DELETE endpoint accepts a pending row: the gallery slot is freed immediately. The one exception is `MEDIA_STORAGE_UNAVAILABLE`, the failure the server promises left the pending row untouched and still confirmable; deleting there would destroy the only recovery state and force a re-upload of an object already sitting in the bucket. So `mediaId` survives on the queue item, and a retry re-confirms that id instead of re-posting several MB over cellular. Any other retry always takes a **fresh** presign, because the previous policy dies with its 5-minute TTL.

Uploads run **sequentially** on the wire, deliberately: one non-terminal row at a time is what makes the queue itself a legible progress affordance. `runQueue` announces «מעלה n מתוך m» per file and then always writes a **terminal** summary into the same region — a run that stopped at the last "מעלה…" would leave every failure silent.

Client-side rejections (`validateUploadFile`, or exceeding `slotsRemaining`) are marked `retriable: false`, since the same file fails identically. They are the one failure with no request and no focus move, so they also raise a separate `role="alert"` batch line — focus is still standing in the file input and a polite region would not reach her.

**Reorder focus follows the photo, not the index**, because the index has just changed underneath. `move` computes a focus key of `${id}:up|down|delete` and picks the *sibling* control when the moved photo lands at an end and its own button becomes disabled; `makePrimary` targets the delete button because both the ↑ and the set-primary action cease to exist at position 0. The refs are populated through a `display:contents` wrapper that reaches the real `<button>`, because the `@boutique/ui` `Button` is a plain function component whose props type carries no `ref`. Reorder is optimistic (`optimistic ?? media`) and the optimistic order is held until the parent hands down a *different* `media` array — clearing on the response instead would flash the old order. A `MEDIA_ORDER_MISMATCH` refetches the dress and announces that the order was re-read.

An `<img>` `onError` means a signed URL expired. The tile falls back to a decorative placeholder and **exactly one** detail refetch is issued per gallery mount (`hasRefreshed` ref), however many URLs expire at once; a failed refresh is swallowed because retrying would just re-request expired URLs.

The file input is a **real, visible, focusable** `<input type="file">` — a `display:none` input plus a label shim breaks Safari/VoiceOver and hides the disabled reason, which is instead appended to the input's own visible label. The Card holds exactly one polite region (storage notice + reorder result + queue summary) and one assertive alert. Arrows are ↑/↓ rather than ←/→ because reorder is a list-position operation that must not invert in RTL, and every icon button carries an `aria-label` that begins with the visible action.

**Hardcoded Hebrew throughout** — this section predates the i18n retrofit and calls no `useTranslation`.

## Depends On

- [[frontend/apps/manage/src/api.ts]] — `api.presignMedia`, `uploadToStorage`, `api.confirmMedia`, `deleteMedia`, `reorderMedia`, `getDress`; `ApiError`, `errorMessage`
- [[frontend/apps/manage/src/validation.ts]] — `MAX_MEDIA_PER_DRESS`, `validateUploadFile`
- [[frontend/packages/ui/src/index.ts]] — `Button`, `Card`, `EmptyState`, `Input`, `Modal`
- [[React]]

## Depended On By

- [[frontend/apps/manage/src/components/DressEditor.tsx]]
- [[frontend/apps/manage/src/__tests__/MediaGallery.test.tsx]]

## Tests

- [[frontend/apps/manage/src/__tests__/MediaGallery.test.tsx]] — the queue states, the transient-503 retry that skips re-upload, the batch-rejection alert, reorder focus, and the expired-URL single refetch

## Notes

`slotsRemaining` is checked against `accepted.length` inside the selection loop, so a multi-file drop that overshoots rejects the *tail* rather than the whole batch. The gallery-full copy explicitly mentions that failed uploads may still be holding slots — pending rows expire on their own after an hour, and nothing in the UI can force that.

Spec and plan: [[.planning/specs/catalog-management.md]] · [[.planning/plans/catalog-management.md]].
