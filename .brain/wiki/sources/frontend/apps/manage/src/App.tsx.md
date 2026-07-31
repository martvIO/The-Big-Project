---
tags: [frontend, manage, react, section-state-machine, authz, navigation]
sources: [frontend/apps/manage/src/App.tsx]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/apps/manage/src/App.tsx
blob: 72e8f1082f2c9e687cb6b051e87e5ea26115c175
commit: a93ff9bec72c63d35742e0c7ad0eae12f8106de6
kind: code
applicability: active
---

# frontend/apps/manage/src/App.tsx

**Role.** The whole console in one component: the session bootstrap (`api.me()` on mount), the login/loading/authenticated three-way branch, the role→nav table, and the section switch. **There is no router** — `section` is a `useState<SectionKey>` and each panel is a `&&` render inside [[frontend/packages/ui/src/components/ConsoleShell.tsx]]. No URL changes, no history entry, no deep link into a section.

**Module.** [[frontend/apps/manage/src/_index]] · **Layer.** app shell

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `App` | component | no props — the root the entry point renders |

`SectionKey`, `NavItem`, `NAV` and `ALL` are module-private.

## Behavior

**Three render states, in order.** Until the `api.me()` promise settles, `bootstrapped` is false and the component returns a bare centred `console.loading` paragraph — this is what stops the login form flashing for an already-signed-in owner. On rejection `staff` stays `null` and [[frontend/apps/manage/src/components/LoginForm.tsx]] renders instead of the shell; `LoginForm` is handed `setStaff` directly, so a successful login re-renders straight into the console with no refetch. `handleLogout` swallows the `api.logout()` rejection deliberately and clears `staff` regardless — a session that is already gone server-side must still let the owner out of the UI.

**`NAV` is the console's single permission-to-UI table, and it is cosmetics.** The control is the server's role gate, which answers a shift manager 403 on every `/manage/staff` route; the filter exists only so she is not shown a door that answers one. `NavItem.roles` is typed `readonly string[]` rather than the literal tuple `as const` would infer, because `staff.role` is whatever `staff_users.role` held and `["owner"].includes(someString)` does not typecheck against a literal tuple.

**`activeKey` is derived at render, never stored, and that is the interesting line.** `handleLogout` clears `staff` but not `section`, so an owner sitting on «צוות» who logs out and hands the front-desk browser to a shift manager would otherwise leave the next user on a panel her role cannot reach. The fallback `reachable[0]?.key ?? section` also survives a role the enum does not know: `GET /manage/auth/me` echoes `staff_users.role` verbatim with no allowlist, such a role matches no `NAV` row, and `reachable[0].key` would throw and white-screen the console. The database CHECK makes that row impossible; the `?.` costs one character and turns an impossible-state crash into an empty nav.

`onNavigate` casts the shell's `string` key back to `SectionKey`. The shell's nav list is rebuilt each render from `reachable` with `t(item.labelKey)`, so the labels follow the i18n bundle rather than being hard-coded here.

## Depends On

- [[frontend/apps/manage/src/api.ts]] — `api.me`, `api.logout`, the `Staff` wire type
- [[frontend/packages/ui/src/components/ConsoleShell.tsx]] — the frame, skip link, nav and `#console-main`
- [[frontend/packages/ui/src/components/Toast.tsx]] — `ToastProvider`, wrapping the whole shell so any section can raise a toast
- [[frontend/apps/manage/src/components/LoginForm.tsx]] — the unauthenticated branch
- [[frontend/apps/manage/src/components/ProfileSection.tsx]], [[frontend/apps/manage/src/components/HoursSection.tsx]], [[frontend/apps/manage/src/components/TypesSection.tsx]], [[frontend/apps/manage/src/components/TermsSection.tsx]], [[frontend/apps/manage/src/components/CatalogSection.tsx]], [[frontend/apps/manage/src/components/BookingsSection.tsx]], [[frontend/apps/manage/src/components/StaffSection.tsx]] — the seven panels
- [[React]] — `useEffect`, `useState`
- [[i18next]] — `useTranslation`

## Depended On By

- [[frontend/apps/manage/src/main.tsx]]
- [[frontend/apps/manage/src/__tests__/Nav.test.tsx]]

## Concepts

- [[Accessibility Compliance]]

## Tests

- [[frontend/apps/manage/src/__tests__/Nav.test.tsx]] — mocks the whole api module with never-settling reads and asserts the role filter and the `activeKey` fallback

## Notes

Only `TermsSection` (`role`) and `StaffSection` (`staffId`) take props from the session; the other five read everything they need themselves. Because the section is component state, a browser refresh always lands the owner back on «פרופיל והגדרות» — accepted, since the console is a small set of settings panels rather than a linkable document space.
