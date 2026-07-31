---
tags: [frontend, storefront, typescript, http-client, wire-types, error-handling]
sources: [frontend/apps/storefront/src/api.ts]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/apps/storefront/src/api.ts
blob: 092e96c45c48c5d36ab3cb2148a9f8d943853f76
commit: a93ff9bec72c63d35742e0c7ad0eae12f8106de6
kind: code
applicability: active
---

# frontend/apps/storefront/src/api.ts

**Role.** The storefront's whole backend contract in one file: a `fetch` wrapper that normalises the house error envelope into `ApiError`, two error→i18n-key mappers, the TypeScript mirror of every `/storefront/*` response shape, the thirteen endpoint calls, and a one-promise memo for the boutique read. Hand-written on purpose — [[frontend/packages/api-client]] is an empty stub and this app declines codegen.

**Module.** [[frontend/apps/storefront/src/_index]] · **Layer.** api

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `ApiError` | class | `{status, code, message}`; `name = "ApiError"` |
| `FALLBACK_ERROR_MESSAGE` | const | the Hebrew used when no envelope could be parsed |
| `isNotFound` | fn | **dress-detail only** — 404, or 400 `VALIDATION_ERROR` |
| `errorMessageKey` | fn | error → i18n key; switches on `code`, never on `message` |
| `errorMessage` | fn | `errorMessageKey` + `t()` |
| `errorMessageOr` | fn | same, but a surface-specific fallback replaces `errors.unknown` |
| `apiFetch<T>` | fn | the wrapper; `credentials: "omit"` on every call |
| `api` | const | `listDresses` · `getDress` · `getBoutique` · `getTerms` · `listAppointmentTypes` · `listSlots` · `sendOtp` · `verifyOtp` · `createBooking` · `lookupBooking` · `confirmAttendance` · `cancelBooking` |
| `getBoutiqueOnce` / `resetBoutiqueCache` | fn | the layout-level single-flight boutique read |
| wire types | interface | `StorefrontMedia` `StorefrontDress` `DressListResponse` `SizeChip` `StorefrontDetail` `HoursRow` `ExceptionRow` `BoutiqueResponse` `StorefrontTerms` `AppointmentTypeRow` `SlotRow` `SlotListResponse` `OtpVerifyResponse` `BookingCreateRequest` `BookingCreateResponse` `ManageBookingFacts` `ManagePolicy` `ManageBoutique` `ManageBookingResponse` |

## Behavior

**`credentials: "omit"` is a contract, including on the mutations.** The booking surface is cookie-blind: the credential is the `verification_token` in the request body, and a backend test asserts that an owner's session cookie changes nothing. Nothing here ever attaches an `Authorization` header — the tenant is resolved from the host, not from the client.

**`errorMessageKey` switches on `code` and never on `message`, and that is the point.** Every backend message is English ("No active boutique at this address.", "Too many attempts. Try again later."), so rendering `ApiError.message` would paint English onto a Hebrew-only page for a suspended tenant, an unknown slug, an archived dress or a throttle trip. Ten codes map to keys; `SMS_NOT_CONFIGURED` and `SMS_UNAVAILABLE` deliberately share one string, because to a visitor "misconfigured" and "provider down" are the same dead end and the way out is the phone either way. Anything unmapped falls back to real Hebrew via `errors.unknown`. `errorMessageOr` exists so a surface can say "we could not load the collection" instead of a generic apology when the code carries nothing.

**`isNotFound` folds a 400 into a 404, and the scope note on it is load-bearing.** A malformed dress id out of a truncated link fails FastAPI's UUID coercion, which the platform normalises to `400 VALIDATION_ERROR` — semantically "no such dress", not "the server broke". Without the fold the page rendered `dress.error` plus a Retry button that re-issued the same 400 forever. But on the booking POST a `400 VALIDATION_ERROR` is a *form* problem, so the booking flow keys off `errorMessageKey` and must never consult this helper — pinned in [[frontend/apps/storefront/src/__tests__/api.test.ts]].

**Two non-obvious cases in `apiFetch` are both real, not defensive padding.** A 204 short-circuits before parsing because `/otp/send` answers with no body by design. And a **200 whose body is not JSON** is converted into an `ApiError` rather than being allowed to escape as a raw `SyntaxError`: under the SPA history fallback, a fetch to `/storefront/dresses` with no backend behind the proxy answers `200 text/html`, which is exactly the state the blocking e2e job runs in — an unhandled `SyntaxError` escapes the page's `catch` and blanks the screen. `extractError` is fully defensive about the envelope's shape and defaults `code` to `"UNKNOWN"` when only a `message` string is present.

**The wire types encode a field allowlist, and the absences are spec requirements.** `price_agorot: number | null` collapses "the owner hid it" and "never set" into one indistinguishable null — the storefront renders both as "מחיר בתיאום" and could not tell them apart if it wanted to. `SizeChip.available` is a boolean, never a count. `SlotRow` carries `starts_at` and nothing else — no capacity, no remaining, because every slot the engine returns is bookable by construction and a `remaining` field would equal capacity exactly on an empty calendar. `HoursRow` is **one row per window, not per day**, so a lunch break survives; grouping is [[frontend/apps/storefront/src/lib/hoursText.ts]]'s job. The `ManageBooking*` block deliberately omits the booking id, the customer's name and phone, the seat index and the notes: the manage link is possession-auth, so the payload carries the appointment's facts and no PII beyond them. The header comment lists the manage-only fields that must stay absent (`price_visible`, `quantity`, `out_of_stock`, `total_quantity`, `variant_count`, `archived`, `capacity`, `sort_order`, timestamps, `toggles`) — the backend never even computes the stock ones.

**`listSlots` sends no window by default, on purpose.** The server defaults to today..+14d in Jerusalem; a client-computed window would read the device clock, which is the class of bug `frontend/scripts/qa-greps.sh` bans mechanically.

**The three manage calls take the token in the POST body, and all three answer the same shape.** POST even for the lookup: a GET would put a live credential in the query string and from there into every access log, proxy trace and `Referer` header on the path. One response type means the page re-renders every state from one branch.

**`getBoutiqueOnce` is a single-flight memo owned by [[frontend/apps/storefront/src/components/StorefrontLayout.tsx]].** The footer needs the boutique block on every page and the body needs it again on `/` and `/about`; one promise per page load covers both. Unlike the dress endpoints this response carries no signed URLs, so nothing goes stale within a session. The `catch` clears the memo before rethrowing — otherwise every retry would replay the same failure and the layout's retry button would be permanently inert. `resetBoutiqueCache` is the test/retry escape hatch.

## Depends On

- [[backend/app/storefront/schemas.py]] — the response models these interfaces mirror
- [[backend/app/booking/schemas.py]] — the booking and manage-lookup shapes

## Depended On By

- [[frontend/apps/storefront/src/components/StorefrontLayout.tsx]] — `getBoutiqueOnce`, `resetBoutiqueCache`, `BoutiqueResponse`
- [[frontend/apps/storefront/src/routes/CatalogPage.tsx]], [[frontend/apps/storefront/src/routes/DressPage.tsx]], [[frontend/apps/storefront/src/routes/AboutPage.tsx]], [[frontend/apps/storefront/src/routes/BookPage.tsx]], [[frontend/apps/storefront/src/routes/ManageBookingPage.tsx]]
- [[frontend/apps/storefront/src/components/ContactCard.tsx]], [[frontend/apps/storefront/src/components/HoursCard.tsx]], [[frontend/apps/storefront/src/components/ShareButton.tsx]], [[frontend/apps/storefront/src/components/booking/SizeChips.tsx]], [[frontend/apps/storefront/src/components/booking/TypePicker.tsx]]
- [[frontend/apps/storefront/src/lib/contact.ts]], [[frontend/apps/storefront/src/lib/hoursText.ts]] — type-only

## Concepts

- [[Tenant Resolution]]
- [[Media Storage]]

## Tests

- [[frontend/apps/storefront/src/__tests__/api.test.ts]] — the error-envelope parsing, the non-JSON-200 case, the `isNotFound` scope, and the code→key table

## Notes

Deliberately a local copy of [[frontend/apps/manage/src/api.ts]] rather than a shared package: the two differ on `credentials` (the console sends cookies, this one omits them) and on error rendering, and hoisting them into `@boutique/api-client` has no consumer pressure yet — see [[frontend/packages/api-client/src/index.ts]], whose header records why codegen was declined.
