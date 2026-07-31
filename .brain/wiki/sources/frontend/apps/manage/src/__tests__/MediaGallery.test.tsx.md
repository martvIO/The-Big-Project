---
tags: [frontend, manage, test, vitest, media, upload, s3, accessibility]
sources: [frontend/apps/manage/src/__tests__/MediaGallery.test.tsx]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/apps/manage/src/__tests__/MediaGallery.test.tsx
blob: efe190bc678c41fb92cce10f048af449e4d88355
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# frontend/apps/manage/src/__tests__/MediaGallery.test.tsx

**Role.** The suite for the three-step photo upload orchestration (presign → upload → confirm) and the gallery around it: strict sequencing, per-file failure isolation with two *different* recovery paths depending on the failure, slot budgeting, keyboard reorder with focus that follows the photo, and signed-URL expiry recovery.

**Module.** [[frontend/apps/manage/src/__tests__/_index]] · **Layer.** test

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `calls` | module state | an append-only string log every mock writes to, so "sequential on the wire" is one assertion |
| `media(id, sortOrder)` / `detail(rows)` / `presign(mediaId)` | helpers | `Media`, `DressDetail`, `PresignResponse` fixtures |
| `photo(name, size)` | helper | a `File` with `size` forced via `defineProperty` (jsdom won't compute it) |
| `renderGallery(overrides)` | helper | mounts with sensible defaults and returns the `onDetail` spy |
| `selectFiles(files)` | helper | fires `change` on the «הוספת תמונות» input |
| `MediaGallery upload orchestration` | suite | sequencing, failure isolation, slot cap, client-side type rejection |
| `MediaGallery storage-disabled state` | suite | the reason on the disabled input's visible label |
| `MediaGallery reorder` | suite | optimistic swap, focus follow, end-of-list disabling |
| `MediaGallery signed-URL expiry` | suite | one refetch per mount, alt text, per-item control naming |

## Behavior

**Sequencing is asserted as an exact array**, not as call counts: two files produce `presign:m1, upload:m1, confirm:m1, presign:m2, upload:m2, confirm:m2`. Overlapping presigns would race the media-slot budget on the server, so file 2 must not begin until file 1 confirms.

The two failure paths are the sharpest thing in the file, and they are deliberately asymmetric. A failed **upload** (or a confirm that fails for any reason other than a storage outage — the `MEDIA_MISMATCH` 409 case) means the pending row is `deleteMedia`d immediately so the gallery slot is freed, and the retry has to start from a fresh presign. A confirm that fails with a **503 `MEDIA_STORAGE_UNAVAILABLE`** leaves the pending row alone: the object already reached the bucket and the server left the row confirmable, so the retry re-confirms the *same* media id — the test pins `presignMedia` and `upload` at exactly one call each. Destroying the row there would force a full re-upload of a file that is already stored. In both cases the queue keeps going: file 2 completes even though file 1 failed.

Retry buttons are named with their file («נסי שוב — IMG_4821.jpg») because three bare «נסי שוב» buttons would be unnavigable from a screen reader's button list. A client-side-rejected type (HEIC, `image/heic` or an empty type from Safari) gets no retry offer at all — retrying an unsupported file cannot succeed.

Reorder is optimistic and the focus contract is the reason the tests exist: after moving photo 1 forward, focus must be on the button that moved *with the photo* (`aria-label="הזזת תמונה 2 קדימה"`), and when the button it used becomes disabled at the end of the list, focus moves to its sibling (`אחורה`) rather than dropping to `<body>`. A `role="status"` announces the new position («התמונה הועברה למקום 2 מתוך 3»).

Signed URLs expire, so an `<img>` `error` triggers a re-read of the dress. The test fires `error` on **both** images and asserts `getDress` ran exactly once — a per-image refetch would stampede on every expired gallery. Per-item controls append the ordinal without replacing the visible text («מחיקה — תמונה 2»), which is the WCAG 2.5.3 contract, and the primary photo carries a caption instead of a redundant set-primary button.

## Depends On

- [[frontend/apps/manage/src/components/MediaGallery.tsx]] — the subject
- [[frontend/apps/manage/src/api.ts]] — media endpoints and `uploadToStorage` mocked; `ApiError` / `errorMessage` are the real ones
- [[Testing Library]] · [[Vitest]]

## Depended On By

Nothing imports a test file. The wire-level half of the same flow is covered by [[frontend/apps/manage/src/__tests__/api.test.ts]]; the file-shape rules by [[frontend/apps/manage/src/__tests__/validation.test.ts]].

## Concepts

- [[Media Storage]] · [[Accessibility Compliance]]

## Notes

`Object.defineProperty(file, "size", …)` is required — jsdom's `File` reports the byte length of the array it was constructed from, which is 3 bytes here. See [[.planning/specs/catalog-management.md]].
