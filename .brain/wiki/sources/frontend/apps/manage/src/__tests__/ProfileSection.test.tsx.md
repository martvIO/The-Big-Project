---
tags: [frontend, manage, test, vitest, settings, disclosure, bidi]
sources: [frontend/apps/manage/src/__tests__/ProfileSection.test.tsx]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/apps/manage/src/__tests__/ProfileSection.test.tsx
blob: c2d89351a6ccd35f73b3fe1b4f6be4cf585f9647
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# frontend/apps/manage/src/__tests__/ProfileSection.test.tsx

**Role.** The smallest component suite in the console, and the only one whose main assertion is about **DOM order**: the "these fields are published" notice must sit under the profile heading and *above* the fields it describes.

**Module.** [[frontend/apps/manage/src/__tests__/_index]] · **Layer.** test

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `settings(profile)` | helper | a `Settings` fixture with both toggles off |
| `ProfileSection public-visibility disclosure` | suite | placement of the disclosure line, pinned from both sides |
| `ProfileSection essence and instagram` | suite | render, `dir` treatment, hint copy, and the save round-trip |

## Behavior

The disclosure test asserts `compareDocumentPosition` three times — heading → notice → address → toggles — rather than merely finding the text somewhere on the page. F10 is the PR that made phone and address world-readable on the storefront, so a disclosure the owner scrolls past *after* typing her home address has already failed; "somewhere before the toggles" would pass a layout that discloses too late.

The instagram field carries `dir="ltr"` because a Latin handle on an RTL page is a numeric-run-style island — the same treatment `maps_url` gets. That is the narrow, correct use of an explicit direction; note the contrast with the Hebrew free-text fields elsewhere in the console, which take a **bare** `<bdi>`. The visible hint «שם המשתמש בלבד, ללא @» is asserted because the server rejects a leading `@` outright, so the rule is stated up front rather than discovered by a 400.

The save test pins the whole round trip: edited values reach `updateSettings` inside a `profile` object that still carries the untouched `phone`, and the form re-renders from the **response**, not from local state — the final `findByLabelText("אינסטגרם")` assertion is what would fail if the component optimistically kept its own draft.

`../i18n` is imported for side effects only; the comment says why — the section renders through `useTranslation`, so without an initialised i18next every Hebrew assertion below would be matching a bare key.

## Depends On

- [[frontend/apps/manage/src/components/ProfileSection.tsx]] — the subject
- [[frontend/apps/manage/src/api.ts]] — `getSettings` / `updateSettings` mocked, `Settings` type real
- [[frontend/apps/manage/src/i18n/index.ts]]
- [[Testing Library]] · [[Vitest]]

## Depended On By

Nothing imports a test file.

## Concepts

- [[Hebrew RTL Bidi]]

## Notes

Coverage here is narrow by design — the hours, types and terms halves of settings live in their own components and suites. See [[.planning/specs/owner-settings.md]] and [[.planning/specs/storefront-browse.md]] for why the disclosure exists at all.
