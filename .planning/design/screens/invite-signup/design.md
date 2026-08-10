# Screen design — F26 Invite-code boutique signup (`apps/platform`: `/platform` invites + `/platform/join`)

**Date**: 2026-08-09 · **Status**: DRAFTED · **Spec**: `.planning/specs/invite-signup.md` (D1–D8, source of truth) · **Extends**: `.planning/design/screens/platform-console/design.md` (F25, shipped) · **Tokens**: `.planning/design/system/tokens.md` — binding

## What this adds

Two surfaces in the **same shipped bundle**, no new app, no new component in `packages/ui`:

1. **Operator side** — an «הזמנות» Card + an «הזמנה חדשה» Card in `Console.tsx`, beside F25's tenants table and provision form. The generated join link is a **one-time secret**; §Screen A2 is the whole delicate part of this feature.
2. **Redeemer side** — `JoinPanel` at `/platform/join#code=…` (a **fragment**, so the credential reaches no server log — spec CONFLICTS #3), the one screen in this app a non-operator ever opens, likely on a phone.

**Components** — all shipped, all already used by this app: `Card` · `Input` · `Button` / `ButtonLink` · `Badge` · `Modal` · `Skeleton` · `EmptyState`. Deliberately unused: `ToastProvider` (F25 ruled success is an inline `role="status"` line — so the clipboard confirmation is a status line, not the storefront's `ShareButton` toast), `ConsoleShell`, `Select`, `Toggle`.

**F-W1 applies without exception**: `Button size="sm"` is `min-h-9` = 36px and fails the 44px floor. `md` is the component default — **no call site in F26 passes `size`**.

## Structure

```
App.tsx   ⚠ branches BEFORE the me() bootstrap: location.pathname === "/platform/join" → JoinPanel
├─ JoinPanel                       anonymous, never calls /platform/auth/me
│  ├─ step "code"     lockup h1 · Card · Input(code) · [המשך]
│  ├─ step "claim"    lockup h1 · Card · <dl> read-only facts · Input(password) · [הקמת הבוטיק]
│  └─ step "done"     lockup h1 · Card · status line · ButtonLink → {slug}.modryn.co.il/manage
└─ Console  (F25, unchanged above)
   Card   h2 platform.invites.heading  → table: name · slug · owner email · status · expires · [ביטול ההזמנה]
   Card   h2 platform.invites.createHeading  → form  ⟷  ONE-TIME LINK PANEL (mutually exclusive, A2 rule 3)
   Modal  revoke confirm  ([חזרה] + danger [ביטול ההזמנה])
```

**Data discipline**: invites are fetched once per console mount; create appends the row locally, revoke removes it (the F25 / `CatalogSection.tsx:78-80` pattern). The reason differs from F25's — `GET /platform/invites` writes no audit row (spec has no `INVITES_LISTED`) — but the shape is kept for consistency and because a refetch would blank the table under the operator.

**Dates**: reuse F25's explicit `timeZone: "Asia/Jerusalem"` rule. `expires_at` is formatted `{ dateStyle: "medium", timeStyle: "short" }` — an expiry stated to the day only is a lie about when the link dies.

---

## Screen A — Operator: invites

### A1 · Create form (Card 2)

Fields are the same three the operator already types in F25's provision form, **minus the password** (D2: the redeemer supplies it). Therefore this form **reuses the shipped keys** `platform.provision.slugLabel` / `slugHelp` / `slugInvalid` / `slugReserved` / `nameLabel` / `ownerEmailLabel` and the shipped `slugProblem()` mirror. *Declared deviation from spec D8's key list* (`platform.invites.slug|name|ownerEmail`): three duplicate strings are a drift surface for zero benefit, and the fields are byte-identical. Only genuinely new copy gets new keys.

No expiry statement before submit — the 14-day TTL is a server setting and `platform.invites.linkExpires` states the real `expires_at` afterwards. Mirroring it client-side would be a new mirrored constant (`test_frontend_constant_parity`).

| State | Treatment |
|---|---|
| default | slug (`dir="ltr"`, live URL preview in `help`) · name · owner email (`type="email" dir="ltr" autoComplete="off"`) · [יצירת הזמנה] |
| client-invalid slug | `Input error` slot, submit not fired |
| submitting | submit `loading` (disabled + `aria-busy`), fields disabled |
| server refusal | `role="alert"` in the form; values intact. `slug_taken` → `platform.error.slug_taken` (shipped), `invalid_or_reserved_slug` → shipped |
| success | the form is **replaced** by the link panel (A2); its values are cleared behind it |

### A2 · The one-time link panel — the code cannot be lost by a mis-click

Nine rules; each exists because of a specific way a one-time secret gets destroyed or leaked.

1. **A panel inside the Card, never a `Modal`.** `Modal` is a native `<dialog>` wired to close on Esc (`onCancel`) — one accidental keypress away from losing the only copy of a credential. It does NOT backdrop-dismiss: native `<dialog>` needs a click-outside handler for that and the shipped component has none, so the Esc risk is the whole of the case. This panel has no dismissal vector at all.
2. **One dismiss control, and its label states the consequence**: «שמרתי את הקישור — סגירה». No ✕ glyph, no auto-dismiss, no timeout.
3. **While the panel is open the create form is not rendered.** A second create cannot clobber an unread code, and the panel cannot scroll out of sight behind a form the operator is retyping into.
4. **The link is a `readOnly` `<input dir="ltr">`, full width, select-all on focus.** `readOnly`, not `disabled` — disabled controls are unfocusable and unselectable, so manual copy would be impossible. An `<input>` scrolls; it never truncates, so no character is hidden behind an ellipsis.
5. **It is never an `<a href>` and there is no "open link" control.** A clicked href puts the live code in browser history (and, on the join page, in a referrer). The operator delivers it; she does not open it.
6. **The copy result is spoken.** Success → `role="status"` «הקישור הועתק.»; failure (no `navigator.clipboard`, insecure origin) → `role="alert"` telling her to select and copy manually — the `ShareButton.tsx` lesson, rendered inline because this app has no `ToastProvider`.
7. **The raw code lives in exactly one React state variable.** Not in `location`, `sessionStorage`, `localStorage`, a `data-*` attribute, the document title, or a `console.log`. Reload, re-login, or any remount → gone, and `GET /platform/invites` never returns it (D6), so the table below cannot re-render it.
8. **Recovery is stated, not discovered.** The panel's own copy ends with «אם הקישור אבד, אפשר לבטל את ההזמנה וליצור אחת חדשה.» — an unrecoverable-feeling moment that is in fact two clicks (spec Open questions: reissue ergonomics).
9. **No channel is implied.** «יש למסור את הקישור לבעלת הבוטיק בעצמך. המערכת אינה מעבירה אותו לאיש.» — F25's `passwordNotice` register verbatim; no form of «נשלח» in any tense, because no outbound channel exists (spec OUT).

| State | Treatment |
|---|---|
| shown | h3 «ההזמנה נוצרה» · summary line (name + `<bdi dir="ltr">` URL) · `linkOnce` warning · readOnly link Input · `linkExpires` · `linkDeliver` · [העתקת הקישור] + [שמרתי את הקישור — סגירה] |
| copied | `role="status"` line under the buttons |
| copy failed | `role="alert"` line, link Input still selectable |
| dismissed | panel unmounts, state cleared, empty create form returns, focus moves to the slug Input |

### A3 · Invites table (Card 1)

Semantic `<table>` in `overflow-x-auto`, `<caption class="sr-only">`, `<th scope="col">` — F25's table verbatim in shape. Columns: **שם** (`<bdi>`) · **כתובת** (`<bdi dir="ltr">`) · **אימייל** (`<bdi dir="ltr">`) · **סטטוס** (Badge) · **בתוקף עד** · actions (`sr-only` th). **No code column exists** (A2 rule 7).

Status — **the word carries the state, colour never does**: open → `Badge success` «פתוחה» · redeemed → `Badge neutral` «נוצלה» · expired → `Badge muted` «פג תוקף», derived client-side from `expires_at < now`. Revoked invites are soft-deleted and simply leave the list; the revoke copy says so rather than letting the row vanish unexplained.

Only an **open** row carries the [ביטול ההזמנה] action. Redeemed and expired rows have none — there is nothing left to do to them.

| State | Treatment |
|---|---|
| loading | `<Skeleton variant="text" lines={4} />` |
| load failed | `role="alert"`, `platform.invites.loadFailed` (outage register, `text-ink-muted`) |
| empty | `EmptyState` `platform.invites.empty`, pointing at the form below |
| loaded | table |
| revoke in flight | that row's button disabled via a per-id busy flag |
| revoke failed | `role="alert"` under the table, mapped by `ApiError.code` |

### A4 · Revoke confirm

F25's suspend precedent unchanged: plain row trigger, `Modal` two-step, `danger` **only** on the footer confirm (table density — see F25 §Screen 3; do not cite either as the house destructive-trigger norm). Focus returns to the row trigger on close.

The footer's cancel is **«חזרה», not «ביטול»** — a dialog whose confirm reads «ביטול ההזמנה» beside a cancel reading «ביטול» is a mis-click generator. New key `platform.invites.revokeCancel`; F25's `platform.suspend.cancel` is untouched.

---

## Screen B — Redeemer: `/platform/join#code=…`

Shape follows `LoginPanel.tsx`: centered, the MODRYN lockup as the single `h1` (decorative `img alt=""`, `aria-hidden` Latin wordmark, `sr-only` Hebrew title), one `Card`. Three steps, one at a time.

⚠ One DELIBERATE departure from that precedent, called out so it is not read as a mis-citation: the column is `max-w-md` (448px) where `LoginPanel.tsx` uses `max-w-sm` (384px). The claim step renders a `<dl>` of three read-only facts rather than login's two inputs, and at 384px the label-over-value stack wraps at 375.

**Bootstrap**: read `code` from `location.hash`; absent → step "code". Present → `POST /platform/join/invite` (code in the body), `Skeleton` + a `role="status"` «בודקים את ההזמנה.» while in flight; 200 → step "claim"; 404 → step "code" with the `invalid_invite` sentence already in its alert slot.

⚠ THIS AUTO-FETCH HAS THE SAME FAILURE MODES AS A MANUAL SUBMIT, AND D5 PUTS IT ON THE SAME BUDGET, so a 429 here is reachable by an owner who merely reloads the link. Every non-200 lands on step "code" with the sentence already in its alert slot — the step is reached BY the failure, so the alert needs no `role="alert"` (focus arrives with it, B1's rule). The mapping is exactly B1's, not a second vocabulary:

| Outcome | Sentence in the alert slot |
|---|---|
| 404 (unknown / expired / redeemed / revoked — one refusal by design, D5) | `platform.error.invalid_invite` |
| 429 | `platform.error.rate_limited` |
| network failure or 5xx | `platform.join.loadFailed` + `platform.join.retry` — the house `{ns}.loadFailed` / `{ns}.retry` pair, mirroring `platform.invites.loadFailed` on the operator side |

These are the SAME keys §5 already defines for a manual submit; the auto-fetch introduces no second vocabulary, only the `loadFailed`/`retry` pair below, which the join namespace previously lacked.


### B1 · Code entry

One `Input` (`dir="ltr"`, `autoComplete="off"`, `inputMode="text"`) + [המשך]. **A pasted full link is accepted**, not just the bare code: the field extracts `code=` from anything URL-shaped before submitting. The owner was given a link, so a link is what she will paste, and rejecting it would spend a limiter attempt on a formatting mistake.

| State | Treatment |
|---|---|
| default | field + `platform.join.codePrompt` in `help` |
| empty submit | native `required`, no request fired (a blank attempt must not spend limiter budget) |
| checking | submit `loading`, `role="status"` line |
| 404 `invalid_invite` | `role="alert"`, one sentence for unknown / expired / redeemed / revoked (D5 anti-enumeration — the UI must not distinguish them) |
| 429 `rate_limited` | `role="alert"`, «יותר מדי ניסיונות…», no countdown (window is server-side) |
| network / unknown | `errorMessage()` fallback |

### B2 · Claim form

Read-only facts first, in a `<dl>`: **שם הבוטיק** (`<bdi>`), **כתובת הבוטיק** (`<bdi dir="ltr">{slug}.modryn.co.il`), **אימייל של בעלת הבוטיק** (`<bdi dir="ltr">`). Then one `Input` — password, `type="password"`, `dir="ltr"`, `autoComplete="new-password"`, `required`, **`minLength={10}`**. No exported constant, no client-computed sentence: the floor is expressed as the attribute (spec trap — `test_frontend_constant_parity` must stay green), and the authoritative Hebrew is the **shipped** `platform.error.password_too_short`, shown as `help` **before** submit so the failure is prevented rather than reported. Preventing it matters: the limiter is failures-only at 5/900s, so three typos could lock an owner out of her own boutique for fifteen minutes.

| State | Treatment |
|---|---|
| default | facts + password field + [הקמת הבוטיק] |
| submitting | submit `loading`, field disabled |
| `empty_password` / `password_too_short` | into the password `Input`'s **`error` slot** (`aria-describedby` + `role="alert"`, associated with the field), not the form-level alert |
| `invalid_invite` (raced: revoked or redeemed between preview and submit) | form-level `role="alert"`; the password field is cleared and the form disabled — there is nothing left to retry |
| `slug_taken` / `invalid_or_reserved_slug` | form-level `role="alert"` with a **join-specific** sentence: the shipped operator copy («הכתובת הזו כבר תפוסה.») tells the owner nothing she can act on. Lookup order is `platform.join.error.{code}` → `platform.error.{code}` → `errorMessage()` |
| `rate_limited` | form-level `role="alert"` |
| success | step "done" |

### B3 · Success

`role="status"` «הבוטיק מוכן.» · a line naming the login email · a `ButtonLink` (default `md`) to `https://{slug}.modryn.co.il/manage`, label «כניסה לניהול הבוטיק», the URL also shown as text in `<bdi dir="ltr">`. The password is **never** repeated back. Back-navigating to this screen and resubmitting is impossible: the code is spent and answers `invalid_invite`.

## Screen C — Gateway connect: deferred by the spec, deliberately not designed here

**Spec D7 scopes the gateway step out of F26 entirely**, so this document designs no gateway UI. F17 shipped the whole surface owner-only at `/manage/gateway` behind `require_role(OWNER)`, on a tenant host that does not exist until B3 succeeds. F26's contribution is the link in B3 and nothing else.

The success copy therefore says **nothing about payments, deposits or gateways**. A new tenant's `settings` is `{}`, so `deposits_enabled` is off and F17's `PolicyBlockerBanner` stays silent until the owner turns deposits on — at which point that shipped banner is the nudge. A "connect your gateway" sentence here would be a promise F26 cannot keep and would put payment copy in a feature that ships no payment code (Gate 1 / Q1).

## Responsive — 375 / 768 / 1440

- **Console**: unchanged from F25 — one column, `max-w-4xl mx-auto px-4`. The invites table scrolls inside its own `overflow-x-auto`; the page never scrolls horizontally. Row actions use `flex-wrap gap-2`.
- **Link panel (A2)**: link Input full width at every size. Buttons `fullWidthMobile` — stacked full-width at 375, inline at ≥640. The dismiss button is always **last in DOM order** so a thumb reaching the bottom of the panel does not land on it before the copy button.
- **Join**: `max-w-md` centered at every width — a one-field form must not stretch to 1440. `px-4` gutters at 375; the `<dl>` stacks label-over-value below 640 and sits two-column above.

## Accessibility — IS 5568 / WCAG 2.0 AA, legal, axe zero-violation

- `<html lang="he" dir="rtl">` (shared bundle). `<bdi dir="ltr">` on every Latin run — slug, email, URL, invite link, code; **bare `<bdi>` around boutique names** (a Hebrew name must not get `dir="ltr"` — the `BookPage.tsx:1156-1166` lesson).
- **One `h1` per screen**: the console header's `platform.heading`; on join, the lockup with its `sr-only` title. Then `h2` per Card, `h3` for the link panel. No level skipped.
- **Focus on step change**: every join step has an `h2` — `platform.join.headingCode`, `platform.join.heading` (claim) and `platform.join.headingDone` — and each carries `tabIndex={-1}` and is focused when its step mounts, so a keyboard or screen-reader user lands on the new content instead of at the top of the document. Same on link-panel dismiss (focus → slug Input) and revoke-modal close (focus → row trigger).
- **`aria-live` for async**: every in-flight operation renders a `role="status"` line (invite check, copy result, revoke result); every refusal renders `role="alert"`. Buttons use the shipped `loading` → `aria-busy` + disabled.
- **Errors associated with fields**: field-scoped refusals go through `Input`'s `error` prop (`aria-describedby` + `role="alert"` on the message, `aria-invalid` on the control). Only non-field refusals use a form-level alert.
- **44px**: every `Button` / `ButtonLink` is the `md` default (F-W1). `focusRing` comes from the shared components. Table row actions included.
- **Not colour alone**: invite status is a worded Badge; the expired row's muted text is redundant with its word.
- **Password**: `autoComplete="new-password"` on the join field — `current-password` would offer the owner an unrelated saved credential.
- **axe zero-violation runs (e2e)**: invites table · create form · link panel · revoke modal · join code step · join claim step · join success · RTL rendering on each.

## Copy deck — `apps/platform/src/i18n/he.ts` + `ar.ts` (untranslated, Q3/#47)

**Zero exclamation marks (#5) and no form of «נשלח» in any tense** — both mechanically enforced by the shipped `__tests__/i18n.test.ts` guard. `he` = `ar` verbatim.

**Interpolated Latin runs carry their isolate inside the string, not at the call site.** Three entries below — `platform.invites.createdFor`, `platform.invites.revokeBody`, `platform.join.successBody` — embed **literal `<bdi>` / `<name>` markup in the Hebrew string** and are rendered with `<Trans>`, **never `t()`**:

```tsx
// Trans, not t(): the url must land inside a bare <bdi dir="ltr">.
<Trans
  i18nKey="platform.invites.createdFor"
  values={{ name: created.name, url: `${created.slug}.modryn.co.il` }}
  components={{ bdi: <bdi dir="ltr" />, name: <bdi /> }}
/>
```

This is the shipped `staff.deactivateBody` precedent verbatim — `StaffSection.tsx:443-454` + `he.ts:294-298` — including its comment, so the next editor does not "simplify" it back to `t()`. **Two tag names, because the two isolates are not interchangeable**: `<bdi>` wraps url / slug / email, which are **always** Latin, so its element takes `dir="ltr"`; `<name>` wraps a boutique name, which may well be Hebrew, so its element is a **bare** `<bdi />` (the `BookPage.tsx:1156-1166` lesson, already §Accessibility's rule). Without the isolate the Latin run reorders on screen against the neutral characters beside it — the comma in `createdFor`, the parentheses in `revokeBody`. Tokens interpolated into these three strings appear **only** inside a tag; a bare `{{token}}` in an RTL sentence is the defect.

F25's shipped `platform.suspend.body` renders a slug through a plain `t("platform.suspend.body", { name, slug })` (`Console.tsx:267`, and no `<bdi>` in its `he.ts` string) — that is the bug shape F26 does not repeat. Fixing it is F25's scope, not this feature's.

### 1. Invites — table

| Key | Notes (EN) | Hebrew |
|---|---|---|
| `platform.invites.heading` | h2 | הזמנות |
| `platform.invites.caption` | sr-only table caption | רשימת ההזמנות שנוצרו |
| `platform.invites.colName` / `colSlug` / `colOwnerEmail` / `colStatus` / `colExpires` / `colActions` | th; actions sr-only | שם · כתובת · אימייל · סטטוס · בתוקף עד · פעולות |
| `platform.invites.statusOpen` | Badge success | פתוחה |
| `platform.invites.statusRedeemed` | Badge neutral | נוצלה |
| `platform.invites.statusExpired` | Badge muted, derived client-side | פג תוקף |
| `platform.invites.empty` | EmptyState, points at the form below | אין עדיין הזמנות. אפשר ליצור את הראשונה בטופס שלמטה. |
| `platform.invites.loadFailed` | outage register | לא הצלחנו לטעון את רשימת ההזמנות כרגע. |

### 2. Invites — create + the one-time link

| Key | Notes (EN) | Hebrew |
|---|---|---|
| `platform.invites.createHeading` | h2 on Card 2 | הזמנה חדשה |
| `platform.invites.createCta` | submit | יצירת הזמנה |
| `platform.invites.createdHeading` | h3 on the link panel | ההזמנה נוצרה |
| `platform.invites.createdFor` | summary; **`<Trans>`**, tags `bdi` + `name` | `ההזמנה נוצרה עבור <name>{{name}}</name>, בכתובת <bdi>{{url}}</bdi>` |
| `platform.invites.linkOnce` | **the one-time warning + the recovery path** (A2 r2, r8) | הקישור מוצג פעם אחת בלבד. אחרי סגירת החלונית לא נציג אותו שוב, וגם לא נשמור אותו. אם הקישור אבד, אפשר לבטל את ההזמנה וליצור אחת חדשה. |
| `platform.invites.linkLabel` | label on the readOnly Input | קישור ההזמנה |
| `platform.invites.linkExpires` | real `expires_at`, Jerusalem time | הקישור בתוקף עד {{date}} |
| `platform.invites.linkDeliver` | no channel exists (A2 r9) | יש למסור את הקישור לבעלת הבוטיק בעצמך. המערכת אינה מעבירה אותו לאיש. |
| `platform.invites.copy` | button | העתקת הקישור |
| `platform.invites.copied` | `role="status"` | הקישור הועתק. |
| `platform.invites.copyFailed` | `role="alert"`, manual path stated | לא הצלחנו להעתיק את הקישור. אפשר לסמן אותו ולהעתיק ידנית. |
| `platform.invites.dismiss` | the single dismiss; label states the consequence | שמרתי את הקישור — סגירה |

### 3. Invites — revoke

| Key | Notes (EN) | Hebrew |
|---|---|---|
| `platform.invites.revokeCta` | plain row trigger | ביטול ההזמנה |
| `platform.invites.revokeTitle` | Modal title | לבטל את ההזמנה? |
| `platform.invites.revokeBody` | immediate; row leaves the list; reissue is possible. **`<Trans>`**, tags `bdi` + `name` — the parentheses are exactly the neutral characters that reorder without an isolate | `הקישור שנמסר עבור <name>{{name}}</name> (<bdi>{{slug}}</bdi>) יפסיק לפעול מיד, וההזמנה תרד מהרשימה. אפשר ליצור הזמנה חדשה לאותה כתובת.` |
| `platform.invites.revokeConfirm` | the `danger` button, the only red in the flow | ביטול ההזמנה |
| `platform.invites.revokeCancel` | **not «ביטול»** — see A4 | חזרה |

### 4. Join

| Key | Notes (EN) | Hebrew |
|---|---|---|
| `platform.join.title` | sr-only h1 under the lockup | MODRYN — הקמת בוטיק |
| `platform.join.checking` | `role="status"` while the preview is in flight | בודקים את ההזמנה. |
| `platform.join.codeLabel` | label | קוד ההזמנה |
| `platform.join.codePrompt` | help; a pasted full link is accepted (B1) | אפשר להדביק כאן את הקישור המלא שקיבלת, או את הקוד בלבד. |
| `platform.join.codeSubmit` | submit | המשך |
| `platform.join.headingCode` | h2 on the code step — the focus target when the step mounts | הזנת קוד הזמנה |
| `platform.join.heading` | h2 on the claim step | הקמת הבוטיק |
| `platform.join.headingDone` | h2 on the done step — the focus target when the step mounts | הבוטיק מוכן |
| `platform.join.claiming` | intro above the read-only facts | אלה הפרטים שאושרו לבוטיק. אם משהו כאן אינו נכון, כדאי לפנות ל‑MODRYN לפני שממשיכים. |
| `platform.join.boutiqueLabel` / `addressLabel` / `emailLabel` | `<dl>` terms | שם הבוטיק · כתובת הבוטיק · אימייל של בעלת הבוטיק |
| `platform.join.password` | label | בחירת סיסמה |
| `platform.join.submit` | submit | הקמת הבוטיק |
| `platform.join.success` | `role="status"` | הבוטיק מוכן. |
| `platform.join.successBody` | password never repeated. **`<Trans>`**, tag `bdi` only (no name token) — `components={{ bdi: <bdi dir="ltr" /> }}` | `אפשר להיכנס לניהול הבוטיק עם האימייל <bdi>{{email}}</bdi> והסיסמה שנבחרה.` |
| `platform.join.toManage` | `ButtonLink`, md | כניסה לניהול הבוטיק |
| `platform.join.loadFailed` | outage register — the bootstrap read failed on network or 5xx (B, Bootstrap) | לא הצלחנו לבדוק את ההזמנה כרגע. |
| `platform.join.retry` | `Button secondary md` beside it | ניסיון נוסף |

### 5. Refusal codes (`ApiError.code`; join looks up `platform.join.error.*` first, then `platform.error.*`, then `errorMessage()`)

| Key | Server code | Hebrew |
|---|---|---|
| `platform.error.invalid_invite` | 404 — **one sentence for unknown / expired / redeemed / revoked** (D5) | ההזמנה אינה תקפה. אפשר לבקש מ‑MODRYN הזמנה חדשה. |
| `platform.error.rate_limited` | 429, no countdown | יותר מדי ניסיונות. אפשר לנסות שוב בעוד מספר דקות. |
| `platform.join.error.slug_taken` | 409 raced between issue and redemption; the owner cannot fix a slug she never chose | הכתובת שהוקצתה לבוטיק אינה פנויה יותר. כדאי לפנות ל‑MODRYN לקבלת הזמנה חדשה. |
| `platform.join.error.invalid_or_reserved_slug` | 400, same instruction | הכתובת שהוקצתה לבוטיק אינה תקינה. כדאי לפנות ל‑MODRYN לקבלת הזמנה חדשה. |
| *(reused, shipped)* | `slug_taken`, `invalid_or_reserved_slug`, `empty_password`, `password_too_short` on the **operator** side | F25 deck §6, unchanged |

## What this surface deliberately does not have

No gateway step (D7 — F17 owns it, link only) · no invite email/WhatsApp send (spec OUT — no channel exists, and no copy may imply one) · no code shown a second time, anywhere, ever (A2) · no one-click reissue (revoke + create; spec Open questions) · no captcha or abuse UI (Q10) · no slug or email field on the redeemer's form (D2) · no audit-log screen (INSERT-only grant, F25 §Screen 5) · no toast system, no client router, no new `packages/ui` component. Each is a spec decision, not an oversight.

Design Gate: accepted by design-critic (round 3), 2026-08-09
