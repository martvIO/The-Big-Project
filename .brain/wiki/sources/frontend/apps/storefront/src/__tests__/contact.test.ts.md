---
tags: [frontend, storefront, test, vitest, contact, whatsapp, waze]
sources: [frontend/apps/storefront/src/__tests__/contact.test.ts]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/apps/storefront/src/__tests__/contact.test.ts
blob: 9f83aef026de73f488154830e3d89905132ce053
commit: a93ff9bec72c63d35742e0c7ad0eae12f8106de6
kind: code
applicability: active
---

# frontend/apps/storefront/src/__tests__/contact.test.ts

**Role.** The unit suite for the two link builders in `lib/contact` — `waPhone` (an Israeli mobile to a `wa.me` digit string) and `wazeUrl` — written specifically to exercise the branches no fixture in the repo would otherwise reach.

**Module.** [[frontend/apps/storefront/src/__tests__/_index]] · **Layer.** test

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `waPhone` | suite | `0`-prefix → `972`, an already-`972` number passes through, everything else is `undefined` |
| `wazeUrl` | suite | `https://waze.com/ul?q=` + `encodeURIComponent(address)`; `undefined` for null/undefined/blank |

## Behavior

The header states the reason the suite is this shaped: this module is the survivor of four near-identical copies, and the copy it replaced (inlined in the dress detail) was missing **both** the empty-digits guard and the already-`972` passthrough. Every phone fixture in the repo is a `0`-prefixed Israeli mobile, so without the cases below exactly one branch would ever execute and either guard could be deleted with a green suite.

**The foreign-number case is a security-flavoured regression guard, not a taste call.** The previous implementation stripped punctuation and returned whatever digits remained, so a service line stored as `"1-800-555"` minted `wa.me/1800555` — a real, reachable WhatsApp account belonging to a stranger. `waPhone("1-800-555")` and `waPhone("+1 415 555 0123")` must both be `undefined`: no link beats a link to the wrong person.

The nullish/blank case adds `"---"`, which is the one the deleted copy actually lacked — punctuation-only input strips to zero digits, and without the guard the function returns `""` and the caller renders `href="https://wa.me/"`.

## Depends On

- [[frontend/apps/storefront/src/lib/contact.ts]] — the subject
- [[Vitest]]

## Depended On By

Nothing imports a test file. `contactChannels()` and `contactLabels()` from the same module are covered where they are rendered, through the `@boutique/ui` `ContactPanel`.

## Notes

The suite covers only the two pure builders; `contactChannels` and `contactLabels` are untested here. `waPhone`'s accept-set is deliberately narrow — Israeli mobiles only — so a boutique that stores an international number simply gets no WhatsApp link rather than a wrong one.
