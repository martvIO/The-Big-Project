# Screen design — F25 Web platform console (`apps/platform`, served at `/platform` on `admin.{base}`)

**Date**: 2026-08-06 · **Status**: DRAFTED, design gate self-approved (assembled from shipped `packages/ui` components, no novel pattern except one declared deviation — the plain row-level suspend trigger, rationale in §Screen 3 — the Q2 argument) · **Spec**: `.planning/specs/platform-console.md` (D1–D8, source of truth) · **Tokens**: `.planning/design/system/tokens.md` — binding

## What this surface is

The operator console for the four tenant-lifecycle operations, at `admin.modryn.co.il/platform`. **A third workspace app (`apps/platform`), not a route in manage** — spec D8: operator screens and strings must never ship in a tenant-served bundle. One authenticated screen, no client router (the manage `App.tsx` pattern): bootstrap `GET /platform/auth/me` → 401 renders the login panel, 200 renders the console. Operator-facing and information-dense is fine; the visual language is the house tokens, nothing new.

## Components — all shipped, nothing new, nothing promoted

From `packages/ui/src/index.ts`: `Card` · `Input` · `Button` · `Badge` · `Modal` · `Skeleton` · `EmptyState` · `focusRing` / `cn` / `tokens`. These are exactly the components manage already uses, which is the whole sharing story: **no new `packages/ui` component, no promotion, no console-only variant**. Deliberately not used: `ConsoleShell` (it is the tenant console's seven-section nav shell; this app has one screen and needs none of it), `Select`/`Toggle`/`SlotPicker`/storefront composites, `ToastProvider` (success is an inline `role="status"` line — one fewer moving part).

**F-W1 ruling applies**: `Button size="sm"` is `min-h-9` = 36px and FAILS the 44px floor. Every button in this app is `md` (44px) — including the per-row table actions. No `sm` anywhere.

## Structure

```
App.tsx        bootstraps GET /platform/auth/me
├─ LoginPanel          (LoginForm.tsx verbatim in shape: lockup-as-h1, Card, two Inputs, submit)
└─ Console
   <header>   h1 platform.heading · operator display_name · [יציאה]  (Button ghost, md)
   Card       h2 platform.tenants.heading
              Input(filter, client-side) · semantic <table> in overflow-x-auto
              rows: name · <bdi dir="ltr">slug</bdi> · status Badge · created date
                    [השהיה] [איפוס סיסמת בעלים]   (both md; plain secondary/ghost in the row)
   Card       <form> h2 platform.provision.heading
              Input(slug, dir=ltr) · Input(name) · Input(owner email, dir=ltr)
              Input(initial password, type=password, autoComplete="new-password")
              <p> platform.provision.passwordNotice · [הקמת בוטיק]
              success line role="status" with the new tenant URL
   Modal      suspend confirm  (footer-supplied [ביטול] + danger [השהיה])
   Modal      reset owner password (its own small form; danger nowhere — it is not destructive)
```

Data discipline: the tenant list is fetched **once** per console mount — every `GET /platform/tenants` writes a `TENANTS_LISTED` audit row (spec conflict 4), so the filter is client-side and mutations **patch rows locally** (the `CatalogSection.tsx:78-80` house pattern): suspend flips the row's status to `suspended`, provision appends a row from the form values. No refetch loops spamming the platform's audit book.

## Screen 1 — Operator login

Shape is `LoginForm.tsx` copied into `apps/platform` (lockup `h1` with `sr-only` Hebrew title, `Card`, email + password `Input`s `dir="ltr"`, full-width submit with `loading`). `autoComplete`: `email` / `current-password`.

| State | Treatment |
|---|---|
| default | form as above |
| submitting | submit `Button loading` (disabled + `aria-busy`) |
| 401 `INVALID_CREDENTIALS` | `<p role="alert" class="text-sm text-danger">` `platform.login.failed` — one generic sentence for wrong password AND unknown email (the timing-equalized anti-enumeration posture, spec D4; the UI must not distinguish either) |
| 429 `TOO_MANY_ATTEMPTS` | same alert slot, `platform.login.tooMany` — states the wait plainly, no countdown (the window is server-side) |
| session expired (any mid-session 401 `NOT_AUTHENTICATED`) | App flips back to the login panel with `platform.login.sessionExpired` in a `role="status"` line above the Card — calm fact, not an error register; the operator's in-progress form values are gone and the copy does not pretend otherwise |

## Screen 2 — Tenant table

Semantic `<table>` (not the manage-staff flex-rows — that pattern exists because `ConsoleShell` caps at 720px; here the operator scans 50+ tenants and columns earn their keep). `<caption class="sr-only">`, `<th scope="col">` throughout.

Columns: **שם** (name) · **כתובת** (slug, `<bdi dir="ltr">`) · **סטטוס** (Badge) · **נוצר** (created_at → `Intl.DateTimeFormat("he-IL", { dateStyle: "medium" })`, UTC in, local out) · actions (`<th>` is `sr-only` «פעולות»).

- **Status**: `active` → `Badge success` «פעיל», `suspended` → `Badge neutral` «מושהה». **The word carries the state, colour never does** (house rule). A suspended row additionally renders its שם/כתובת cells `text-ink-muted` and its [השהיה] action is absent — the only action left on it is the password reset.
- **Filter**: one `Input` with a real `<label>` (`platform.tenants.filterLabel`), substring match on name+slug, client-side (see data discipline above). Zero matches renders `platform.tenants.filterNoMatch` in a `role="status"` row — not `EmptyState`, which is reserved for the true-empty platform.
- No pagination, no server-side search, no sorting controls: 50-tenant scale (spec Problem), one screen, first-fetch order (service returns `created_at` order).

| State | Treatment |
|---|---|
| loading | `<Skeleton variant="text" lines={5} />` in place of the table |
| load failed | `<p role="alert" class="text-sm text-ink-muted">` `platform.tenants.loadFailed` — the outage register |
| empty (zero tenants) | `EmptyState` with `platform.tenants.empty` pointing at the provision form below — a fresh platform's first screen must explain itself |
| loaded | table as above |
| filter, no match | `platform.tenants.filterNoMatch` status row |
| row action in flight | that row's buttons disabled via a per-slug busy flag |
| row action failed | `<p role="alert" class="text-sm text-danger">` under the table, mapped by error code (§copy 6) |

## Screen 3 — Row actions

**Suspend — two-step modal confirm, with one declared deviation from the shipped precedent.** Both shipped destructive call sites put `variant="danger"` on the trigger button itself AND on the modal confirm (`StaffSection.tsx:342-352` deactivate row action; `DressEditor.tsx:401` archive trigger). This screen deliberately deviates on the trigger only: the row's [השהיה] stays plain (secondary/ghost) and `danger` appears ONLY in the modal footer. Rationale — table density: those precedents show one red trigger on a short staff list or a single editor; here, at 50+ tenant rows, matching them would paint a column of red buttons, one per active row, and the salience red exists to provide would be gone. The two-step mechanics themselves are the precedent unchanged: row action opens a shared `Modal`, confirm/cancel in the footer. **Plan/build note**: do not cite this row as the house destructive-trigger pattern — StaffSection/DressEditor (danger on the trigger too) remain the norm; this is a table-density exception. Title `platform.suspend.title`, body `platform.suspend.body` — it states the two facts that make the tap informed: it bites immediately, and **there is no un-suspend in this console** (spec OUT — first real reversal request owns it; the body says so plainly rather than hiding it). Footer: [ביטול] (secondary) + [השהיה] (`danger`, the only red in the flow). Focus restores to the row's trigger on close (the `DressEditor.tsx:130-136` effect — the trigger survives here, but the effect is kept for the failure-path close). No typed-confirmation: the repo's destructive pattern is two-step modal confirm, and the spec names exactly that; a typed slug would be a new pattern this gate cannot self-approve.

**Reset owner password** — `Modal` with a two-field form: owner email (`Input dir="ltr"`, must match the boutique's registered owner — the service checks, the help text says so) and new password (`type="password"`, **`autoComplete="new-password"`** — without it the browser offers the operator's own console credential, the manage-staff lesson). The operator types the password and hands it to the owner out of band — the same trust shape as the CLI's stdin and manage's staff-create (spec D5). **The console never holds a lasting secret**: the password exists only in the field; on success the modal closes, the field state is discarded, and the success line (`role="status"`, `platform.reset.done`) repeats the hand-it-over instruction **without the password**. No generated temp password, no reset link — no such machinery exists (F26 owns invites) and the copy may not imply a channel (§0 rule 2 of the F51 deck: no form of «נשלח», ever). Failure (`owner_not_found`, `tenant_not_found`) renders in the modal's own alert slot; the modal stays open with values intact.

## Screen 4 — Provision form

Second `Card`, always rendered under the table (it is the empty state's target). Fields, each with a visible `<label>`:

- **Slug** (`dir="ltr"`): client validation mirrors `Backend/app/tenancy/slugs.py` — `^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$` plus the 12-word reserved list (`admin api app assets cdn docs mail staging static status support www`) — as an `Input error`-slot message before submit ever fires. The `help` slot shows the resulting URL live: «הכתובת תהיה {{slug}}.modryn.co.il» in `<bdi dir="ltr">`. Server remains authoritative: `invalid_or_reserved_slug` / `slug_taken` map to their own sentences (a suspended boutique still holds its slug — the `slug_taken` copy says «תפוסה», not «קיימת», because the operator cannot see soft-deleted rows).
- **Name**, **Owner email** (`dir="ltr"`, `autoComplete="off"`), **Initial password** (`type="password"`, `autoComplete="new-password"`), followed by the D2-style notice `platform.provision.passwordNotice` — delivery is the operator's to do, nothing is sent, no channel exists.

| State | Treatment |
|---|---|
| default | form |
| client-invalid | per-field `Input error` slot, submit not fired |
| submitting | submit `loading`, fields disabled |
| server refusal | mapped sentence in the form's `role="alert"` slot (§copy 6); values intact |
| success | form clears (password leaves memory), `role="status"` success line with the new tenant URL as an `<a>` in `<bdi dir="ltr">` — `https://{{slug}}.modryn.co.il` — and the row appears in the table above |

## Screen 5 — Audit trail visibility: none, by construction

The spec has **no audit read surface** and cannot grow one here: `platform_audit_log` is INSERT-only for `app_user` (the `REVOKE ALL` / `GRANT INSERT` posture) — the web process is *unable* to SELECT the book it writes. Reading it stays an owner-role/SSH act (R12). Recorded so its absence is never read as an oversight.

## Responsive — 375 / 768 / 1440

One column at every width; content capped `max-w-4xl mx-auto px-4` (wider than manage's 720 — the table earns it). The table sits in its own `overflow-x-auto` container: at 375 it scrolls horizontally inside the container, the page never does. Both forms stack their fields full-width; modal is the shared `Modal` (already viewport-safe). Nothing else changes per breakpoint.

## Accessibility — IS 5568 / WCAG 2.0 AA is a legal requirement; internal audience changes nothing (pre-decided #38)

- `<html lang="he" dir="rtl">`; every Latin run (slug, email, URL, MODRYN wordmark) in `<bdi dir="ltr">`; bare `<bdi>` around tenant names (Hebrew names must not get `dir="ltr"` — the `BookPage.tsx:1019-1022` lesson).
- One `h1` per state: the login lockup's `sr-only` title, or the console header's `platform.heading`; then `h2` for the two Cards. No level skipped.
- Table: `caption` (sr-only), `th scope="col"`, real text in every cell — status is a worded Badge, never colour alone.
- All touch targets 44px: **every `Button` is `md`** (F-W1 — `sm` is 36px and banned here); `focusRing` on every control via the shared components.
- Both `Modal`s: focus trap + focus restore to trigger (shipped behaviour + the DressEditor effect); `Esc` and [ביטול] close without acting.
- Every `Input` has a visible `<label>`; helps in the `help` slot (`aria-describedby`-linked); errors in the `error` slot / `role="alert"`; successes `role="status"`.
- Password fields: reset + provision use `autoComplete="new-password"`; login uses `current-password`.
- axe zero-violation gate (e2e): login, table, provision form, both modals, RTL — the spec's test plan already names these runs.

## Copy deck — `apps/platform/src/i18n/he.ts` + `ar.ts` (untranslated, Q3/#47) · zero exclamation marks (#5), mechanically enforced by the copied `i18n.test.ts` guard · no form of «נשלח» in any tense (no channel exists)

### 1. Login and session

| Key | Notes (EN) | Approved Hebrew (`he` = `ar`) |
|---|---|---|
| `platform.login.title` | sr-only h1 under the lockup | MODRYN — ניהול הפלטפורמה |
| `platform.login.email` | label | אימייל |
| `platform.login.password` | label | סיסמה |
| `platform.login.submit` | submit | כניסה |
| `platform.login.failed` | 401, one sentence for both causes | האימייל או הסיסמה אינם נכונים. |
| `platform.login.tooMany` | 429, no countdown | יותר מדי ניסיונות כניסה. אפשר לנסות שוב בעוד מספר דקות. |
| `platform.login.sessionExpired` | calm status, not an alert | ההתחברות הסתיימה. יש להיכנס שוב. |
| `platform.heading` | console h1 | ניהול הפלטפורמה |
| `platform.logoutCta` | ghost button | יציאה |

### 2. Tenant table

| Key | Notes (EN) | Approved Hebrew |
|---|---|---|
| `platform.tenants.heading` | h2 | בוטיקים |
| `platform.tenants.filterLabel` | visible label on the client-side filter | סינון לפי שם או כתובת |
| `platform.tenants.colName` / `colSlug` / `colStatus` / `colCreated` / `colActions` | th; actions sr-only | שם · כתובת · סטטוס · נוצר · פעולות |
| `platform.tenants.statusActive` | Badge word carries the state | פעיל |
| `platform.tenants.statusSuspended` | Badge word | מושהה |
| `platform.tenants.empty` | EmptyState, points at the form below | אין עדיין בוטיקים במערכת. אפשר להקים את הראשון בטופס שלמטה. |
| `platform.tenants.filterNoMatch` | status row | אף בוטיק אינו תואם את הסינון. |
| `platform.tenants.loadFailed` | outage register | לא הצלחנו לטעון את רשימת הבוטיקים כרגע. |
| `platform.tenants.suspendCta` | row action, plain (red only in modal) | השהיה |
| `platform.tenants.resetCta` | row action | איפוס סיסמת בעלים |

### 3. Suspend confirm

| Key | Notes (EN) | Approved Hebrew |
|---|---|---|
| `platform.suspend.title` | Modal title | להשהות את הבוטיק? |
| `platform.suspend.body` | immediate + no console un-suspend, stated plainly; slug via `<bdi>` | הבוטיק {{name}} (‎<bdi>{{slug}}</bdi>‎) יפסיק להיות זמין ללקוחות ולצוות מיד. אין בקונסולה פעולת הפעלה מחדש. |
| `platform.suspend.confirm` | the `danger` button | השהיה |
| `platform.suspend.cancel` | secondary | ביטול |

### 4. Reset owner password

| Key | Notes (EN) | Approved Hebrew |
|---|---|---|
| `platform.reset.title` | Modal title, names the boutique | איפוס סיסמה — {{name}} |
| `platform.reset.emailLabel` | label | אימייל של בעלת הבוטיק |
| `platform.reset.emailHelp` | why it is asked again | חייב להתאים לבעלת הבוטיק הרשומה. |
| `platform.reset.passwordLabel` | label | סיסמה חדשה |
| `platform.reset.notice` | no lasting secret, no channel | יש למסור את הסיסמה החדשה לבעלת הבוטיק בעצמך. המערכת אינה מציגה אותה שוב. |
| `platform.reset.submit` | submit | איפוס סיסמה |
| `platform.reset.done` | status line, password NOT repeated | הסיסמה אופסה. יש למסור אותה לבעלת הבוטיק בעצמך. |

### 5. Provision form

| Key | Notes (EN) | Approved Hebrew |
|---|---|---|
| `platform.provision.heading` | h2 — the spec's «בוטיק חדש» form | בוטיק חדש |
| `platform.provision.slugLabel` | label | כתובת (תת־דומיין) |
| `platform.provision.slugHelp` | live URL preview, `<bdi dir="ltr">` | הכתובת תהיה {{slug}}.modryn.co.il |
| `platform.provision.slugInvalid` | client mirror of the slug regex | הכתובת יכולה להכיל אותיות לטיניות קטנות, ספרות ומקפים בלבד. |
| `platform.provision.slugReserved` | client mirror of RESERVED_SLUGS | הכתובת הזו שמורה למערכת ואינה זמינה. |
| `platform.provision.nameLabel` | label | שם הבוטיק |
| `platform.provision.ownerEmailLabel` | label | אימייל של בעלת הבוטיק |
| `platform.provision.ownerPasswordLabel` | label | סיסמה ראשונית |
| `platform.provision.passwordNotice` | the D2 line, verbatim register from F51 | יש למסור את הסיסמה לבעלת הבוטיק בעצמך. המערכת אינה מעבירה אותה לאיש. |
| `platform.provision.submitCta` | submit | הקמת בוטיק |
| `platform.provision.done` | success + URL link in `<bdi dir="ltr">` | הבוטיק הוקם. הכתובת: {{url}} |

### 6. Error codes → Hebrew (keyed on `ApiError.code`; unlisted codes fall through to `errorMessage()`)

| Key | Server code (spec D5) | Approved Hebrew |
|---|---|---|
| `platform.error.slug_taken` | 409 — «תפוסה», not «קיימת»: a suspended boutique still holds its slug | הכתובת הזו כבר תפוסה. |
| `platform.error.invalid_or_reserved_slug` | 400 server backstop of the two client checks | הכתובת אינה תקינה או שמורה למערכת. |
| `platform.error.empty_password` | 400, normally caught client-side | יש להזין סיסמה. |
| `platform.error.tenant_not_found` | 404 on a row action racing a change | הבוטיק לא נמצא. כדאי לרענן את הרשימה. |
| `platform.error.owner_not_found` | 404 in the reset modal | האימייל אינו תואם את בעלת הבוטיק הרשומה. |

## What this surface deliberately does not have

No un-suspend (spec OUT — first real reversal owns it), no audit-log screen (INSERT-only grant, above), no operator management UI (CLI-only, spec D2), no pagination/sorting/server search (50-tenant scale), no TOTP enrolment (D6 recorded risk), no invite emails (F26), no toast system, no client router, no new `packages/ui` component. Each is a spec decision, not an oversight.

Design Gate: accepted by design-critic, 2026-08-06
