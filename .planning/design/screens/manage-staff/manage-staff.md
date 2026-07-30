# Screen design — F51 Staff management (`apps/manage`, section «צוות»)

**Date**: 2026-07-30 · **Status**: DRAFTED, design gate self-approved under Interview **Q2** · **Spec**: `.planning/specs/staff-management.md` (D1–D9) · **Copy**: `./copy.md` · **Tokens**: `.planning/design/system/tokens.md` — binding

## What this screen is

The seventh console section, **rendered only for an owner**. She sees the boutique's live staff, adds one, renames one, changes one's role, resets one's password, and deactivates one. It is the only surface in the product that can create a `shift_manager`, which is why the three sections queued behind it cannot be exercised until it ships.

## Components — all shipped, nothing new, nothing promoted

`Card` · `Input` · `Select` · `Button` · `Badge` · `Modal` · `Skeleton` — every one exported from `packages/ui/src/index.ts` today. **No new `packages/ui` component and no promotion**, which is also the Q2 self-approval argument. `EmptyState` is deliberately *not* used: the list can never be empty, because the acting owner is always in it.

## Structure — `components/TypesSection.tsx`, verbatim in shape

```
<h2>  staff.heading
Card
  <ul>  one <li> per live staff row
        default:  displayName · <bdi dir="ltr">email</bdi> · role Badge · [עריכה] [השבתה]
        editing:  Input(name) · Select(role) · Input(new password, type=password)
                  [+ Input(current password) on her own row when a new password is typed]
                  [שמירה] [ביטול]
Card
  <form>
    <h3>  staff.createHeading
    Input(email) · Input(name) · Select(role) · Input(password, type=password)
    <p>   staff.passwordNotice
    [הוספה לצוות]
Modal (confirm deactivate, footer-supplied [ביטול] [השבתה])
```

Props: `{ staffId: string }` — the acting owner's id, taken from `App.tsx`'s already-fetched `Staff`. The section makes no second identity call.

## Every state

| Screen | State | Treatment |
|---|---|---|
| List | loading | `<Skeleton variant="text" lines={4} />` |
| List | load failure | `<p role="alert" className="text-sm text-ink-muted">` — the **outage** register (`staff.loadFailed`) |
| List | empty | cannot happen; her own row carries `staff.selfMarker` instead |
| List | loaded | rows as above, muted «זו את» on her own |
| Row | editing | inline `Input` / native `Select` / password `Input` |
| Row | action failure | `<p role="alert" className="text-sm text-danger">` — the **fix-this** register |
| Create | submitting | button disabled via the `TypesSection.tsx:170-180` `creating` flag |
| Deactivate | confirm | shared `Modal`, confirm in a caller-supplied `footer`, plus the `DressEditor.tsx:130-136` focus-restore effect |

Mutations **patch the list row from the mutation response** rather than refetching (`CatalogSection.tsx:78-80`) — two views that render one object cannot disagree.

## Responsive

Content is capped at 720px by `ConsoleShell`, which is why the list is **rows and not a table**. Rows are `flex flex-wrap`, so at 375px the meta and the two buttons wrap under the name rather than overflowing; the edit fields are already a wrapping row. Nothing scrolls horizontally at any of 375 / 768 / 1440. `Card`'s baked-in `p-6` is not overridden — `cn()` is a plain join and a consumer `p-0` loses at equal specificity.

## Accessibility — IS 5568 / WCAG 2.0 AA is a **legal** requirement (pre-decided #38)

- Nav item is `ConsoleShell`'s plain `<nav>` button with `aria-current="page"` and `aria-controls="console-main"`. **No `role="tab"` anywhere.**
- One `h1` (the shell's, `sr-only`) → this section's `h2` → the create form's `h3`. No level skipped.
- Every `Input` and `Select` carries a real `<label>`; role is a **native** `<select>`.
- 44×44 minimum targets: `Button`'s shipped `py-*`/`text-base` sizing, no `min-h` literal.
- Visible focus ring on every control — `focusRing` from `packages/ui`, inherited through the shared components.
- Contrast checked against `tokens.md`, not eyeballed. The role Badge's `success` / `neutral` variants both pass AA as text at `text-xs`, and **the Hebrew word carries the role** — colour never does.
- **Bidi**: `<bdi dir="ltr">` around the email (a Latin run inside RTL); a **bare** `<bdi>` around `display_name`, because `dir="ltr"` on a Hebrew name is itself a bidi defect (`BookPage.tsx:1019-1022`).
- Both password fields are `type="password"` with **`autoComplete="new-password"`** — without it the owner's browser offers her *own* console credential for the new staffer's account, which is a real way to create an account nobody can sign into.
- The confirm `Modal` restores focus to its trigger: the trigger unmounts while the dialog is open, so native `<dialog>` focus-return would land on `<body>`.

## What this screen deliberately does not have

No search, no pagination (single-digit rows), no archived-staff list, no restore control, no email edit, no audit-history view. Each is a spec decision (D5, D6, D8), not an oversight.
