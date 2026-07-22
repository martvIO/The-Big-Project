# Pattern: Diff configs when migrating a scaffold

When replacing or migrating a scaffold/app tree, explicitly compare the old tree's config files (`.oxlintrc.json`, `.eslintrc*`, `tsconfig`, formatter configs) against the new one — `git show <base>:<old-path>` — rather than relying on tool defaults to reproduce prior guardrails.

**Origin (2026-07-21, Feature 1 review):** migrating `Frontend/App` → `frontend/apps/*` dropped `.oxlintrc.json`; oxlint's zero-config default silently misses `react/rules-of-hooks` violations, so the hooks safety net vanished while `pnpm -r lint` stayed green. Caught only by empirical review.
