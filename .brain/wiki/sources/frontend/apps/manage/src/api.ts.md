---
tags: [frontend, manage, typescript, api-client, wire-types, error-handling]
sources: [frontend/apps/manage/src/api.ts]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/apps/manage/src/api.ts
blob: 1836861860819e7ca4b17f76b80ccfc68012bdad
commit: a93ff9bec72c63d35742e0c7ad0eae12f8106de6
kind: code
applicability: active
---

# frontend/apps/manage/src/api.ts

**Role.** The console's entire backend surface in one hand-written file: a `fetch` wrapper (`apiFetch`), the `ApiError` type every section catches, ~30 TypeScript interfaces mirroring the Python schemas **verbatim in snake_case**, and the `api` object holding every `/manage/*` call. No generated client, no case-conversion layer — [[frontend/packages/api-client/src/index.ts]] is a deliberately empty stub whose header records why codegen was declined.

**Module.** [[frontend/apps/manage/src/_index]] · **Layer.** api client

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `FALLBACK_ERROR_MESSAGE` | const | the one Hebrew sentence shown when the server's message cannot be read |
| `ApiError` | class | `Error` + `{status, code}`; `code` is the house envelope's `error.code` or `"UNKNOWN"` |
| `errorMessage(error)` | fn | `ApiError` → its message, anything else → the fallback. Every section's catch path |
| `apiFetch<T>(path, {method, body})` | fn | the wrapper: `credentials: "include"`, JSON in/out, throws `ApiError` on non-2xx |
| `uploadToStorage(presign, file)` | fn | the S3 POST-policy upload — deliberately **not** routed through `apiFetch` |
| `api` | const object | the endpoint map: auth, settings, appointment types, availability, terms, dresses/variants/media, bookings, slots, staff |
| wire types | interfaces | `Staff`, `Settings`, `AppointmentType`, `Availability`, `TermsHistory`, `Dress`/`DressDetail`, `OwnerBookingRow`/`OwnerBookingDetail`, `OwnerSlotRow`, `StaffMember`, … |

## Behavior

**`apiFetch` sends the session cookie on every call** (`credentials: "include"`) and sets `Content-Type: application/json` only when there is a body — a bodyless POST with a JSON content type is the kind of thing a strict server or a CORS preflight objects to. On a non-ok response it tries `response.json()` inside a `try`, because the failure it is guarding is a **proxy or HTML error page**, not a missing field; `extractError` then validates the `{error: {code, message}}` envelope structurally and only trusts `message` if it is a string. Anything short of that yields `ApiError(status, "UNKNOWN", FALLBACK_ERROR_MESSAGE)`, so no section ever renders `undefined` or a raw English framework sentence into an RTL console.

**`uploadToStorage` is the one call that must not look like the others.** It sends `credentials: "omit"` (the session cookie must never travel to the bucket), sets **no headers at all** so the browser can mint the multipart boundary itself — `Content-Type` for S3 is a form *field*, not a header — and appends `file` **last**, because S3 ignores every field after `file`. It also catches the `fetch` rejection explicitly: a down network or a failed CORS preflight rejects with a bare `TypeError` rather than returning a non-ok `Response`, so without that catch the owner would see an unhandled error instead of `UPLOAD_BLOCKED`.

**The wire types encode several server-side decisions worth not re-litigating.** `OwnerBookingRow` carries no phone and no notes — the day list is deliberately not a bulk PII export of the boutique's whole day — and `OwnerBookingDetail` adds them only when the owner opens one booking. `OwnerSlotRow` carries `capacity` **and** `remaining`, which the anonymous storefront slot row fences off, because the owner legitimately needs to know whether a reschedule target is about to take the last place. `OwnerBookingDetail.manage_link_issued` is a boolean and never the token: `manage_token_hash` is the stored half of a live credential.

**Booking transitions are four verb sub-paths** (`/confirm`, `/cancel`, `/no-show`, `/complete`) rather than one PATCH with a status field, because the guards and side effects differ per transition. `correctBookingPhone` sends the phone **exactly as typed** — there is no client-side normalizer, since a third hand-written copy of the Israeli-mobile normalizer could refuse a legal number or display an E.164 different from the one actually stored on the row whose SMS link is about to rotate. `updateDress` is a full replace (every field sent, so an omitted key can never silently clear a value) while `updateStaff` is genuinely partial (an omitted key means unchanged, and an all-unchanged patch is a server-side no-op that writes no audit row). `listManageSlots` uses `from`/`to`, which are the router's query **aliases**, not the Python parameter names.

## Depends On

- [[backend/app/auth/schemas.py]], [[backend/app/boutique/schemas.py]], [[backend/app/catalog/schemas.py]], [[backend/app/booking/schemas.py]] — the Python models these interfaces mirror by hand; drift here is silent
- [[TypeScript]]

## Depended On By

- [[frontend/apps/manage/src/App.tsx]]
- [[frontend/apps/manage/src/lib/booking.tsx]] — `ApiError`, `errorMessage`
- [[frontend/apps/manage/src/components/LoginForm.tsx]], [[frontend/apps/manage/src/components/ProfileSection.tsx]], [[frontend/apps/manage/src/components/HoursSection.tsx]], [[frontend/apps/manage/src/components/TypesSection.tsx]], [[frontend/apps/manage/src/components/TermsSection.tsx]], [[frontend/apps/manage/src/components/CatalogSection.tsx]], [[frontend/apps/manage/src/components/DressEditor.tsx]], [[frontend/apps/manage/src/components/VariantMatrix.tsx]], [[frontend/apps/manage/src/components/MediaGallery.tsx]], [[frontend/apps/manage/src/components/BookingsSection.tsx]], [[frontend/apps/manage/src/components/BookingDetail.tsx]], [[frontend/apps/manage/src/components/RescheduleDialog.tsx]], [[frontend/apps/manage/src/components/StaffSection.tsx]]

## Concepts

- [[Media Storage]]

## Tests

- [[frontend/apps/manage/src/__tests__/api.test.ts]] — envelope extraction, the non-JSON fallback, and the upload's credential/field ordering rules

## Notes

Wire shapes are snake_case on purpose and stay snake_case all the way into component state — there is no `keysToCamel` layer in this app, so a `camelCase` property name on one of these interfaces is a bug, not a style choice. `PresignResponse.fields` is bearer material valid for 300s: never log it, never render it, never persist it.
