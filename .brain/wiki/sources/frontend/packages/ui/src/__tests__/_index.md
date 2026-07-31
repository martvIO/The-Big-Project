---
tags: [frontend, typescript, test]
sources: [frontend/packages/ui/src/__tests__]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/packages/ui/src/__tests__
blob: 11670215fd05fbbff0d062a586af9d82222f6574
commit: 13d107b8b16f1f2676f1cdb1c994f95822fe2ba0
kind: directory
applicability: active
---

# frontend/packages/ui/src/__tests__/

**Purpose.** Vitest suites pinning each primitive's contract, including the design-token guard that certifies contrast ratios rather than leaving them to the eye.

**Parent.** [[frontend/packages/ui/src/_index]]

## Files

- [[frontend/packages/ui/src/__tests__/A11y.test.tsx]] — Two tests, one per export of [[frontend/packages/ui/src/components/A11y.tsx]], pinning the only two facts about them that jsdom can see: `SkipLink` is a real anchor whose `href` reaches the fragment it was given, and `VisuallyHidden`…
- [[frontend/packages/ui/src/__tests__/Badge.test.tsx]] — A single test over [[frontend/packages/ui/src/components/Badge.tsx]] that pins the non-negotiable half of the badge contract: whatever the variant, the *word* is rendered and findable. Colour is decorative; the text carries the meaning.
- [[frontend/packages/ui/src/__tests__/Button.test.tsx]] — Pins the loading contract, the motion-token contract and — uniquely in this suite — a **byte-exact markup snapshot** of `Button`, written as a regression fence around the extraction of `ButtonLink` beside it in…
- [[frontend/packages/ui/src/__tests__/Card.test.tsx]] — Two tests over [[frontend/packages/ui/src/components/Card.tsx]]: children reach the paper surface, and the hover-elevate affordance is **opt-in** — absent unless `hoverElevate` is passed.
- [[frontend/packages/ui/src/__tests__/DressCard.bidi.test.tsx]] — The bidi-isolation contract for the dress name, split out of the main catalog suite into its own file because it is a *correctness* rule of the RTL product rather than a card feature: the name is always wrapped in a bare `<bdi>`, for Latin…
- [[frontend/packages/ui/src/__tests__/Input.test.tsx]] — Covers **two** components — [[frontend/packages/ui/src/components/Input.tsx]] and [[frontend/packages/ui/src/components/TextArea.tsx]] — pinning the shared field contract: a real label association, an error wired through `aria-invalid` +…
- [[frontend/packages/ui/src/__tests__/Modal.test.tsx]] — Pins the **dismiss-is-never-confirm** contract of [[frontend/packages/ui/src/components/Modal.tsx]]: Esc closes and fires `onClose` alone, while the destructive action fires only from the caller's own footer button. Three tests, all around…
- [[frontend/packages/ui/src/__tests__/Toast.test.tsx]] — Pins the live-region politeness split of [[frontend/packages/ui/src/components/Toast.tsx]] — success is `role="status"`, error is `role="alert"` — plus the one-at-a-time replacement policy, auto-dismiss, and the provider-less no-op…
- [[frontend/packages/ui/src/__tests__/catalog-composites.test.tsx]] — The largest test file in the package: the full image-lifecycle contract for the three catalog components — [[frontend/packages/ui/src/components/DressCard.tsx]], [[frontend/packages/ui/src/components/DressGrid.tsx]] and…
- [[frontend/packages/ui/src/__tests__/chrome-composites.test.tsx]] — The suite for the storefront's persistent page chrome — the fixed booking bar, the contact link block, and the first-party accessibility menu. Two of its assertions are not behavioral at all but *class-string* assertions, deliberately…
- [[frontend/packages/ui/src/__tests__/console-composites.test.tsx]] — The suite for the three owner-console composites — the app frame, the onboarding checklist, and the missing-cancellation-policy banner. Its sharpest assertion is negative: the console nav must never become a `role="tab"` set.
- [[frontend/packages/ui/src/__tests__/display-primitives.test.tsx]] — The small suite for the three purely presentational primitives — loading skeleton, empty state, section heading. Short by design: what these components owe is the AT contract (hidden vs. announced, correct heading level), not behavior.
- [[frontend/packages/ui/src/__tests__/form-primitives.test.tsx]] — The suite for the four non-text form controls — `Select`, `Toggle`, `Checkbox`, and the native `DateField`/`TimeField` wrappers. Its centre of gravity is `Checkbox`, whose six cases pin the legal-consent semantics that separate it from…
- [[frontend/packages/ui/src/__tests__/hours-composites.test.tsx]] — The suite for the three storefront-header composites: `Price` (the only money renderer in the product), `HoursTable` (the Sun-first Israeli week), and `BoutiqueHeader`.
- [[frontend/packages/ui/src/__tests__/hours.test.ts]] — The pure-function suite for the opening-hours engine in [[frontend/packages/ui/src/lib/hours.ts]] — week grouping, the Jerusalem day index, "next open day", and today's windows. No DOM, no React; the whole file is arithmetic over an…
- [[frontend/packages/ui/src/__tests__/tokens.test.ts]] — The design-token guard, and the most unusual test in the repo: it reads `src/theme.css` and `src/components/Button.tsx` off disk as **text**, parses the `@theme` block into a map, and *computes* WCAG relative luminance from the token hexes…
- [[frontend/packages/ui/src/__tests__/url.test.ts]] — The scheme-allowlist suite for `safeHref` — the single gate every tenant-supplied URL (`maps_url`, Waze) passes before it can reach an `href`.
