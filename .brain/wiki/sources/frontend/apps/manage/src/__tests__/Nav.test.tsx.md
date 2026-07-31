---
tags: [frontend, manage, test, vitest, rbac, navigation, app-shell]
sources: [frontend/apps/manage/src/__tests__/Nav.test.tsx]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/apps/manage/src/__tests__/Nav.test.tsx
blob: dfb01219ed77e8e7c1e240bc0da5c558245af5a7
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# frontend/apps/manage/src/__tests__/Nav.test.tsx

**Role.** The suite for the console's role-filtered section nav — that an owner sees seven items and a shift manager six, that an *unknown* role yields an empty nav instead of a white screen, and that a role handover mid-session cannot strand the new user on a panel she cannot reach.

**Module.** [[frontend/apps/manage/src/__tests__/_index]] · **Layer.** test

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `staff(role)` | helper | a minimal `Staff` fixture whose only interesting field is `role` |
| `NAV_LABELS` | const | the seven Hebrew section labels in their rendered order; the shift-manager set is `.slice(0, 6)` |
| `navItems()` | helper | the nav's button text, read with `queryAllByRole` inside `getByRole("navigation")` |
| `the console nav is role-filtered` | suite | owner / shift manager / out-of-enum role / "cosmetics only" |
| `an unreachable section falls back to the first reachable one` | suite | the logout-and-hand-over path |

## Behavior

**Despite the filename there is no `Nav.tsx`** — the subject is [[frontend/apps/manage/src/App.tsx]], which owns both the nav and the `section` state. Every section `App` mounts fetches on mount, so the API mock hands back a client whose reads return `new Promise(() => {})` and never settle; the sections render their loading state and are covered by their own suites. Only `me`, `login` and `logout` are real `vi.fn()`s.

`navItems()` uses `queryAllByRole` rather than `getAllByRole` deliberately: an out-of-enum role reaches no row at all, and "the nav is empty" has to be an *assertion*, not a thrown query. That case is real — `GET /manage/auth/me` echoes `staff_users.role` verbatim with no allowlist, so an unknown string can reach the component. Every row is then unreachable, the cosmetics fail closed (which is right), and the guard must answer with an empty nav rather than reading `reachable[0].key` off an empty array. Migration `0011`'s CHECK constraint is what makes the row impossible in the first place; a white screen would be the worse of the two failures.

One test asserts a *sentence*: the nav is cosmetics only, and the server's `RoleGate` is what actually refuses. It is pinned as a test so that a later "simplification" of the server gate has to delete this deliberately — a shift manager reaching `/manage/staff` by any other route gets a 403, which [[frontend/apps/manage/src/components/StaffSection.tsx]] maps to Hebrew.

The last suite walks the real handover: an owner sitting on «צוות» logs out and hands the front-desk browser to a shift manager. `handleLogout` clears `staff` but **not** `section`, so without the fallback she would land on a dead panel. The test drives logout → login-as-shift-manager through the real form and then waits for `aria-current="page"` to have moved to the first reachable section.

## Depends On

- [[frontend/apps/manage/src/App.tsx]] — the subject
- [[frontend/apps/manage/src/api.ts]] — mocked; `Staff` type is real
- [[frontend/apps/manage/src/i18n/index.ts]] — side-effect import so labels resolve
- [[Testing Library]] · [[Vitest]]

## Depended On By

Nothing imports a test file.

## Concepts

- [[Fail Closed Defaults]]

## Notes

The file name is the one trap here: search for `Nav` in `src/components/` and you will find nothing. Rename it and the suite is untouched; the coverage it provides belongs to `App.tsx`.
