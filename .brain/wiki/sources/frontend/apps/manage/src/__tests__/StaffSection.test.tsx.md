---
tags: [frontend, manage, test, vitest, staff, rbac, axe, accessibility, bidi]
sources: [frontend/apps/manage/src/__tests__/StaffSection.test.tsx]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/apps/manage/src/__tests__/StaffSection.test.tsx
blob: ed17710e550cc3747c8bcb57d089d92105b3d573
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# frontend/apps/manage/src/__tests__/StaffSection.test.tsx

**Role.** The F51 staff-management suite: list states, bidi per field, create with the "you deliver the password yourself" notice, inline edit that sends only what moved, the self-row's two special cases (no role control, current-password required), a confirmed deactivate with a full focus contract, and three `axe.run()` passes at zero violations.

**Module.** [[frontend/apps/manage/src/__tests__/_index]] · **Layer.** test

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `ME` / `HER` | const | the acting owner's id and the other staffer's — the whole self-vs-other split turns on these |
| `member(overrides)` / `OWNER` | fixtures | a `StaffMember`; `OWNER` is `ME`, role `owner` |
| `renderInShell(node)` | helper | `<main>` + the console's sr-only `<h1>`, so axe scans the real frame |
| `rowFor(name)` | helper | the `<li>` containing a name — **every row query must be scoped through this** |
| Suites | — | list · bidi · create · inline edit · self edit · deactivate · accessibility |

## Behavior

`rowFor` is not convenience, it is correctness: the create form carries the **same labels** («שם לתצוגה», «סיסמה», «תפקיד») and the same two role words as every inline edit, so an unscoped `getByLabelText` is ambiguous by construction rather than by accident. Every mutation assertion is `within(row)`-scoped.

Role is carried by the **word** («בעלת הבוטיק» / «אחראית משמרת»), never by a class, and the acting owner's own row is marked «זו את» with no deactivate button drawn at all — the server refuses a self-deactivate with a 409, and not drawing the button is the cosmetic half of that, so she is never offered a door that refuses. Bidi splits per field: the Latin email is `<bdi dir="ltr">`, the Hebrew display name is a **bare** `<bdi>`, and `bdi[dir='rtl']` is asserted to appear nowhere.

The create form says out loud that the system delivers nothing — «יש למסור את הסיסמה לעובדת בעצמך. המערכת אינה מעבירה אותה לאיש.» — which is literally true (there is no mailer and no SMS sender id) and is the same fact the copy-register guard in [[frontend/apps/manage/src/__tests__/i18n.test.ts]] enforces from the other side. The password input is `type="password"` with `autocomplete="new-password"` so the browser cannot offer the *owner's own* credential into a field that creates someone else's account. A successful create appends the row from the mutation response with `listStaff` still at **one** call — the two views cannot disagree because there is only one source.

Client-side refusals come first (short password, empty address, and `dana@bella`, which the browser's own `type="email"` check accepts), each asserted to leave `createStaff` uncalled. Server refusals are mapped to Hebrew per code — `DUPLICATE_EMAIL`, `LAST_OWNER_REQUIRED`, `STAFF_SELF_MANAGE`, `NOT_AUTHORIZED` — with an explicit fall-through case (`TOO_MANY_ATTEMPTS`) proving unmapped codes still surface the server's own message rather than nothing.

**The self row is where the security shape shows.** Editing herself offers no role control at all: self-demotion is a lockout the console cannot undo, because the router is owner-only and she could not promote herself back. A new password on her own row reveals a «הסיסמה הנוכחית שלך» field that is absent until she types, and the patch carries `current_password`; resetting *someone else's* password never sends one, and the test asserts the field is not even rendered there. A wrong current password renders in Hebrew with the server's `current_password is required and must match` asserted **absent** from the DOM.

Deactivation is confirmed in a native `<dialog>` that names the staffer and states the two facts that make it safe to tap — it bites on her next action, and it is undoable by re-creating the account. The name is isolated in a bare `<bdi>`, tested with `"dana (bella)."` because `ProvisioningService` seeds every founding owner with `display_name = owner_email`, so a Latin run inside a Hebrew sentence is the norm here and reorders at its neutral edges without an isolate; the dialog is also asserted not to contain the literal text `<bdi>`, i.e. the markup is markup. Cancelling returns focus to the trigger; **confirming** moves focus to the `<h2>`, because the trigger unmounts with its row and restoring to it would land on `<body>`.

The accessibility suite is the statutory floor made mechanical (IS 5568 / WCAG 2.0 AA is a legal requirement in this product): axe at zero violations on the loaded list, with a row open for editing, and with the confirm dialog open. Two structural checks back it up — the outline is exactly `H1, H2, H3` with **dialog headings filtered out** (the shipped `Modal` always renders its own `<h2>` into the DOM whether open or not), no `role="tab"` anywhere, and every `input`/`select` in the container has an id with a matching `label[for]`.

## Depends On

- [[frontend/apps/manage/src/components/StaffSection.tsx]] — the subject
- [[frontend/apps/manage/src/api.ts]] — four staff endpoints mocked; `ApiError` / `errorMessage` real
- [[frontend/apps/manage/src/i18n/index.ts]] · [[frontend/apps/manage/src/test/setup.ts]] — the jsdom `<dialog>` stub
- [[axe-core]] · [[Testing Library]] · [[Vitest]]

## Depended On By

Nothing imports a test file. The nav-side half of the same role gate is in [[frontend/apps/manage/src/__tests__/Nav.test.tsx]]; the bounds in [[frontend/apps/manage/src/__tests__/validation.test.ts]].

## Concepts

- [[Hebrew RTL Bidi]] · [[IS 5568 Accessibility]] · [[Fail Closed Defaults]]

## Notes

`screen.getByRole("dialog", { hidden: true })` is required rather than a plain `getByRole("dialog")`: the jsdom stub sets `open` without any of the modal semantics, so the element is treated as hidden. See [[.planning/specs/staff-management.md]] and [[.planning/specs/staff-roles-gating.md]].
