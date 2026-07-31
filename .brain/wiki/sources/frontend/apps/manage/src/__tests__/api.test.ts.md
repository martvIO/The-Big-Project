---
tags: [frontend, manage, test, vitest, api-client, fetch, s3, wire-contract]
sources: [frontend/apps/manage/src/__tests__/api.test.ts]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/apps/manage/src/__tests__/api.test.ts
blob: 5198c97d31a540f0968c6e831e41dd5efef6fb78
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# frontend/apps/manage/src/__tests__/api.test.ts

**Role.** The wire-contract suite for the console's hand-written fetch client: error extraction from the house error envelope, request mechanics (cookies, JSON, id encoding), the S3 direct-POST upload, and the exact path/method/body of every catalog, booking and staff endpoint.

**Module.** [[frontend/apps/manage/src/__tests__/_index]] · **Layer.** test

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `jsonResponse(status, body)` | helper | a real `Response` with a JSON content type |
| `stubFetch(makeResponse)` | helper | stubs global `fetch` with a **factory** — a `Response` body is single-use, so each call gets a fresh one |
| `photo()` | helper | a small JPEG `File` |
| `presign` / `BOOKING_ID` | const | a full `PresignResponse` with the real AWS field set, and a booking UUID |

Suites: `apiFetch` error extraction · `apiFetch` request mechanics · `uploadToStorage` · catalog endpoints · owner booking endpoints · staff endpoints.

## Behavior

Error extraction has three cases and the last two matter most: the house shape `{ error: { code, message } }` yields a typed `ApiError`, but a **non-JSON** body (an HTML 502 from a proxy) and a JSON body **without** the envelope both fall back to `code: "UNKNOWN"` and the Hebrew `FALLBACK_ERROR_MESSAGE`. Without that, a gateway's English HTML would reach an RTL console. Every request carries `credentials: "include"` — the console authenticates by cookie — and every resource id is `encodeURIComponent`-ed, asserted with ids containing a space and a slash (`"a b/c"` → `a%20b%2Fc`).

**`uploadToStorage` is the only call in the app that must *not* look like the others**, and three assertions pin that. It posts with `credentials: "omit"` (an S3 presigned POST rejects a request carrying cookies) and with **no `headers` object at all** — the browser has to set the multipart boundary itself, and `Content-Type` travels as a form *field*, not a header. The form appends every presign field in the server's iteration order with `file` **last**, which is what the bucket's policy requires. A 204 resolves without touching the body, and a 403 rejects as `UPLOAD_FAILED` with a Hebrew message while explicitly **not** parsing the XML error body — `json` and `text` are spied on and asserted never called. A rejected `fetch` (network down, or a CORS preflight that never returns a `Response`) is a bare `TypeError`, and is mapped to a distinct `status: 0` / `UPLOAD_BLOCKED`; the two codes are what [[frontend/apps/manage/src/__tests__/MediaGallery.test.tsx]] branches its recovery on.

The endpoint suites read as a checklist of the manage API's actual shape, which is **not** the RPC style described in the vendored `.claude/rules`: `PUT /manage/settings`, `PUT /manage/dresses/{id}/variants` (one full-matrix replace), `PUT /manage/dresses/{id}/media/order` (a full permutation), `PATCH /manage/staff/{id}`, `DELETE /manage/staff/{id}`, and booking transitions as bare `POST`s to verb sub-paths (`/confirm`, `/cancel`, `/no-show`, `/complete`) **with no body**. An empty `search` is omitted rather than sent as a blank filter. `listManageSlots` uses the `from`/`to` aliases the router binds, unlike the customer-facing slot route.

Two bodies are asserted verbatim for a reason. Staff creation sends the backend's `snake_case` spelling as written — there is no case-conversion layer in this app — and phone correction sends the number **exactly as typed**, because the server normalises and the console deliberately has no client-side phone validator.

## Depends On

- [[frontend/apps/manage/src/api.ts]] — the subject, imported for real (this is the one suite in the directory that does not mock it)
- [[Vitest]] — `vi.stubGlobal`, `vi.spyOn`

## Depended On By

Nothing imports a test file. Every component suite mocks the module this one verifies, so a drift between them is only caught here.

## Concepts

- [[Media Storage]]

## Notes

`vi.unstubAllGlobals()` in `afterEach` is what keeps the `fetch` stub from leaking. The staff-409 loop re-stubs `fetch` inside the loop for the same single-use-body reason. See [[.planning/specs/owner-booking-management.md]] and [[.planning/specs/staff-management.md]].
