---
tags: [frontend, storefront, i18n, hebrew, copy, accessibility]
sources: [frontend/apps/storefront/src/i18n/he.ts]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/apps/storefront/src/i18n/he.ts
blob: 7361e546a58e4f10f5017ae644d57d60db283c67
commit: a93ff9bec72c63d35742e0c7ad0eae12f8106de6
kind: code
applicability: active
---

# frontend/apps/storefront/src/i18n/he.ts

**Role.** Every visible string on the public site, in one `as const` object under twelve sections. This is the *only* place Hebrew may be written — no component, and no other module, may hardcode a visitor-facing string.

**Module.** [[frontend/apps/storefront/src/i18n/_index]] · **Layer.** app shell

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `he` | const | `{ translation: { … } }`, `as const` — the i18next resource bundle |

Sections, in file order: `document` · `catalog` · `dress` · `about` · `hours` · `errors` · `gallery` · `booking` · `manage` · `contact` · `footer` · `statement`.

## Behavior

**`document` is one entry per `RouteName`** and is consumed by `DOC_TITLE_KEYS` in [[frontend/apps/storefront/src/router.tsx]] — one title for all five booking steps and one for all six manage states, both deliberately coarse (see that page). **`errors` is the target of `errorMessageKey`** in [[frontend/apps/storefront/src/api.ts]], which is what keeps English backend messages off a Hebrew page. **`booking.nameRequired` / `nameTooLong` / `notesTooLong` / `phoneInvalid` / `invalidCharacters`** are read by [[frontend/apps/storefront/src/validation.ts]] through `i18n.t()` rather than being restated as literals there.

**`hours.days` is a seven-item, Sunday-first array**, feeding `HoursTable.dayLabels` and [[frontend/apps/storefront/src/lib/hoursText.ts]]'s `todayLine`. It must be read as `t("hours.days", { returnObjects: true }) as string[]`: nothing in this repo declares `CustomTypeOptions` resource typing, so a bare `t()` is typed `string` and the cast is what keeps the blocking `pnpm -r typecheck` step green.

**Several strings encode a product rule rather than a label.** `catalog.priceOnRequest` ("מחיר בתיאום") occupies the same slot at the same height as a real price so a mixed grid never jumps — the wire cannot distinguish "hidden" from "never set", and this string covers both. `dress.unavailable` is a *size*-level marker, not the dress-level out-of-stock badge the storefront never renders; it exists as words because a dimmed chip alone is colour-only signalling, which IS 5568 forbids. `dress.unavailableDress` gives an archived dress the same copy as an unknown id, matching the backend's deliberately indistinguishable 404. `statement.coordinatorNoChannel` covers the tenant that published neither phone nor Instagram *and* the tenant whose boutique fetch failed — §35 wants a reachable channel, so it names the boutique instead of showing an empty contact list.

Interpolation uses i18next `{{name}}` placeholders; `escapeValue` is off (React escapes), configured in [[frontend/apps/storefront/src/i18n/index.ts]].

## Depends On

Nothing — a pure data module with no imports.

## Depended On By

- [[frontend/apps/storefront/src/i18n/index.ts]] — registered as the `he` resource
- every component and route in the app, indirectly through `useTranslation`
- [[frontend/apps/storefront/src/__tests__/i18n-keys.test.ts]] — imports `he` directly to derive the section allowlist

## Tests

- [[frontend/apps/storefront/src/__tests__/i18n-keys.test.ts]] — scrapes dotted-literal keys out of every non-test `.ts`/`.tsx` under `src/`, resolves each against `he.translation`, and asserts it is defined, non-empty, not the key echoed back, and actually contains Hebrew once `{{placeholders}}` are stripped. It also asserts the scanner found more than 40 keys, so a scanner that silently matches nothing cannot make the suite vacuous.

## Notes

i18next answers a miss with the bare key, so a renamed entry renders `statement.limitsAlt` into a Hebrew page — and a rendering test written as `t("statement.limitsAlt")` keeps passing, because both sides degrade to the same ASCII literal. That defect class is invisible to rendering tests; the key test above is the only thing that catches it.

The bundle carries `statement.updated` ("עודכן לאחרונה: 28.7.2026") as a hand-maintained date — it will not update itself when the accessibility statement changes.
