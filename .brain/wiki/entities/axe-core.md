---
tags: [frontend, accessibility, testing, compliance, wcag]
sources: []
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
kind: entity
applicability: n/a
---

# axe-core

**Purpose.** The automated accessibility checker. axe-core 4.12.1, entered two different ways: `AxeBuilder` from `@axe-core/playwright` in [[frontend/e2e/a11y.spec.ts]] and [[frontend/e2e/storefront.spec.ts]], and the raw `run()` imported straight from `axe-core` inside [[Vitest]] suites in the manage console — [[frontend/apps/manage/src/__tests__/BookingsSection.test.tsx]], [[frontend/apps/manage/src/__tests__/StaffSection.test.tsx]], [[frontend/apps/manage/src/__tests__/BookingDetail.test.tsx]].

**These assertions are a legal floor, not a quality target.** Every scan is pinned to `withTags(["wcag2a", "wcag2aa"])` and asserted `toEqual([])`, because WCAG 2.0 AA is **IS 5568**, legally required for this product in Israel. See [[Accessibility Compliance]].

**A green axe run proves less than it looks like.** `page-has-heading-one` is best-practice, not A/AA, so axe passes a heading-less page — several route files say so in comments. SC 2.2.2 (Pause, Stop, Hide) has no axe rule at all, so a non-conformant auto-updating view ships green. The e2e helpers also wait for real content before scanning, since axe against a skeleton passes trivially.

Only [[frontend/apps/manage/package.json]] declares `axe-core`; the storefront's jsdom suites do not use it and get their coverage from [[Playwright]] instead. The manage harnesses wrap the component under test in a `<main><h1 class="sr-only">…` frame, reproducing the console shell that owns its single `h1` rather than scanning a headless fragment.
