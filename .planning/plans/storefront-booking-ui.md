# Plan: Feature 14 — Storefront Booking UI (Epic E3)

**Spec**: `.planning/specs/storefront-booking-ui.md` · **Design**: `.planning/design/screens/booking/booking.md` (rev 2) · **Copy**: `.planning/design/screens/booking/copy.md` · **Branch**: `feature/storefront-booking-ui` · **Created**: 2026-07-29

**Read `booking.md`'s two reconciliation tables before starting any task.** R1–R6 resolve conflicts between the parallel design authors; R7–R31 resolve round 1 of adversarial review. Several sections still argue positions those tables overturned, and the tables win. Four rulings (**R9, R10, R19, R25**) correct specs that the shipped `packages/ui` components **cannot execute** — read those before writing any layout code.

**Three amendments this feature must make to documents it does not own**, all in the same PR: the spec's contract table (`dress_size` is required whenever `dress_id` is sent), the spec's State matrix (three missing rows — boutique-fetch-failed, submit-failed-outside-the-designed-set, and entry-read-failed), and `components.md` (the `BookingCTA` row is stale, plus the new primitives in §13).

TDD throughout. Local gate per task: `make lint` + `make test` for backend tasks, `pnpm -r lint && pnpm -r test` for frontend ones. `frontend/scripts/qa-greps.sh` must stay clean from Task 7 onward.

**Blocked until**: the user signs off `.planning/design/screens/booking/copy.md` (the Hebrew is theirs to author) and confirms gate proposals P1–P5 in `booking.md` §14.

---

## The `packages/ui` split, ruled

The spec calls this "the largest unknown in the estimate". Resolved against the shipped code:

| Candidate (spec §What `packages/ui` does not have) | Verdict | Why |
|---|---|---|
| **Checkbox** | **new in `packages/ui`** | The one genuine gap. `Toggle.tsx` is a native `<input type="checkbox">` but hardcodes `role="switch"` with no opt-out — wrong semantic for one-shot legal consent. New component = Toggle's structure minus the role, plus `Input`'s error/`aria-describedby` wiring. A second app (manage) plausibly needs it. |
| **`ButtonLink`** | **new in `packages/ui`, in `Button.tsx`, sharing its private constants** | Needed by P1. A sibling component rendering `<a href>` with the same `base`/`variants`/`sizes`/`focusRing`, and deliberately **no `loading`, no `disabled`, no `type`, no `ref`** — a link can be none of those, and a "disabled anchor" is the commonest way a design system ships an unreachable control. `Button` itself is untouched. |
| **`ref` on `Input` / `TextArea` / `Select`** | **GATE CONDITION — one line in three files, must land with or before the build** | `id` is `Omit`'d and no `ref` is declared, so **there is today no way to programmatically focus a field**. That makes focus-to-first-invalid and the `OTP_INVALID` focus-retention *unbuildable* — and those are the flow's two WCAG 3.3.1 behaviours. `Button.tsx:12` already has the one-line shape (`ref?: Ref<HTMLButtonElement>`) to copy, because React 19's ref-as-prop is not part of `*HTMLAttributes`. |
| Phone input forced LTR | **nothing to build** | `Input` extends `InputHTMLAttributes` and spreads `...rest`, so `<Input dir="ltr" inputMode="tel" autoComplete="tel" />` is complete. `components.md` already documents Input's "`dir` override for phone/URL fields". |
| OTP code input | **nothing to build** | Same passthrough: `dir="ltr" inputMode="numeric" autoComplete="one-time-code" maxLength={6}`. A segmented six-box widget is ruled out by the design gate (paste + iOS autofill + AT cost). |
| Date picker | **nothing** | Native `<input type="date">`; `DateTimeFields.tsx` already ships the styled native pair. |
| Stepper / progress indicator | **app-local** | One flow in the product has steps. `<ol aria-label>` + `aria-current="step"`, ~25 lines. Promoting it buys a design-gate obligation for a one-consumer component. |
| Radio group | **app-local, native radios** | The type picker's rows carry duration, deposit branch, and an audience badge; a generic `RadioGroup` would need slots for all of it. `<fieldset>` + `<input type="radio">` gets keyboard/AT behaviour free. Not `Select` — duration and deposit must be readable *before* choosing. |
| Chip / segmented control | **app-local** | Size chips and slot chips are both radio-semantics chips shaped by this flow (D4's selectable-when-unavailable rule is unique to it). |
| Slot grid | **app-local** | Spec already says so. |
| Form/fieldset wrapper, form-level error summary | **skip (YAGNI)** | D2's step split means no step has more than two fields. `Input` already renders per-field errors with `role="alert"` + `aria-describedby`; submit-level errors are one app-local `role="alert"` block. |
| Client validation utilities | **app-local `src/validation.ts`** | Spec says so; `apps/manage/src/validation.ts` is the precedent (pure functions → Hebrew string or `null`, exported bound constants that the parity test scrapes). |

Net: **one new component, one new export, zero changes to any existing `packages/ui` render.**

## P1, ruled concretely — the CTA becomes a link

The spec's D1 says the CTA "navigates". It does not say what element that is, and the choice has a wider blast radius than Risk 3 records.

- `shouldIntercept` (`router.tsx:105-146`) + the root delegation (`router.tsx:180-194`) already upgrade any same-origin plain-left-click `<a href>` into a client navigation, while letting modifier-clicks fall through to the browser. So an anchor needs **no new router work**.
- `Button` (`packages/ui/src/components/Button.tsx:53`) renders a hardcoded `<button>` with no `as`/`asChild`.
- **All four shipped CTA assertions query `byRole("button")`** — `AboutPage.test.tsx:282`, `:295`; `CatalogPage.test.tsx:152`, `:183`; `DressPage.test.tsx:254`. Spec Risk 3 names three *behavioural* assertions; the role change touches **every query**, including ones Risk 3 does not mention. Recorded here because a plan that says "invert three assertions" under-counts the diff.

**Ruling**: a new `ButtonLink` in `packages/ui` renders `<a href="/book/slot[/{dressId}]">` with the primary button's styling. A control whose whole job is to change the URL is a link — screen readers announce it as one, the URL is inspectable, and open-in-new-tab (which `router.tsx:117-120` says storefront users do constantly) keeps working through the existing delegation with no new router code. Declined: `<Button onClick={navigate}>` (smaller diff, but announces "button" for a navigation and breaks new-tab); adding `href` to `Button` (leaves `disabled`, `type` and `loading` reachable on an anchor branch, where each is a lie); and exporting the class recipe for three call sites to compose (three unlinted copies of the token strings).

**The href must be absolute**: the delegated handler pushes `anchor.getAttribute("href")` — the raw attribute, not the resolved `.href` — so a relative href would be pushed verbatim and break.

---

## Task 1 — Backend: `GET /storefront/terms`
`Backend/app/storefront/{schemas,service,router}.py`
- New narrow response model in `schemas.py`: exactly `{version, terms_text, refundable_until_hours_before, forfeit_percent}`. **Not** a subclass of `TermsVersionResponse` — the module docstring forbids it and a test asserts non-inheritance. Built field-by-field, never by serialising the row: `id`, `tenant_id`, `created_by` and the timestamps must not reach the wire.
- `service.py`: read the current version via the existing `TermsVersionsRepository.current()` (already shipped, returns `TermsVersion | None`); `None` ⇒ the `NOT_FOUND` path (D5).
- `router.py`: `@router.get("/terms")` on the **existing GET-only router**, so it inherits both router-level dependencies — `_no_store` **and `_throttle`**.

## Task 2 — Backend: arm the guards (TDD — write first, watch it fail)
`Backend/tests/test_storefront_api.py`
- Add `"/storefront/terms"` to the hand-maintained literal path set. This is deliberately manual so that adding a public surface **must fail one test on purpose**; adding the row is what arms the five derived guard suites (no-auth, no-cache, tenant-not-exempt, no-manage-field-leak, throttle-not-inert).
- Explicit cases: field allowlist (`created_by`, `tenant_id`, `id` absent from the response), no-terms ⇒ `404 NOT_FOUND`, cross-tenant isolation, `no-store`, cookie-blindness.
- Order: this task's tests are written **before** Task 1's implementation.

## Task 3 — `apiFetch` grows a body, and seven error codes get Hebrew
`Frontend/apps/storefront/src/api.ts`, `src/__tests__/api.test.ts`
- `apiFetch<T>(path, init?: {method, body})` — copy the shape from `apps/manage/src/api.ts`, but **keep `credentials: "omit"`**: the booking route is cookie-blind by contract and a backend test asserts an owner cookie changes nothing. The verification token travels in the body, never a cookie.
- `errorMessageKey` gains **seven cases over six keys** (`SMS_NOT_CONFIGURED` and `SMS_UNAVAILABLE` share `errors.smsUnavailable`). Do **not** add cases for `NOT_FOUND`, `TOO_MANY_ATTEMPTS`, `VALIDATION_ERROR` — already mapped.
- New typed calls + wire interfaces mirroring the Python schemas verbatim in `snake_case` (no case conversion on this app): terms, appointment-types, slots, dress detail, otp send, otp verify, bookings.
- **`isNotFound` must stay unreachable from the booking flow** — it counts `400 VALIDATION_ERROR` as "dress not found", so reusing it on a booking call would render "השמלה כבר לא זמינה" for a mistyped phone. Assert this.

## Task 4 — `src/validation.ts` + the parity guard
`Frontend/apps/storefront/src/validation.ts`, `src/__tests__/validation.test.ts`, `Backend/tests/test_frontend_constant_parity.py`
- `validateName` (80), `validateNotes` (500), `validatePhone` — pure functions returning a Hebrew string or `null`, per the `apps/manage` precedent.
- **Phone normalisation happens exactly once, here**, before any of the three calls that carry it. A client that normalises differently across `/otp/send`, `/otp/verify` and `/bookings` produces `PHONE_NOT_VERIFIED` for a correct code.
- The cap mirrors the **domain** bound 500, not Pydantic's `MAX_NOTES_INPUT_LENGTH = 2000`; both answer the same `400 VALIDATION_ERROR` and the client cannot tell them apart.
- Generalise `test_frontend_constant_parity.py` (currently a text scrape against one hard-coded path with an explicit `MIRRORED_CONSTANTS` tuple) to read **both** validation files, and add the two D7 rows: `MAX_CUSTOMER_NAME_LENGTH` (80), `MAX_BOOKING_NOTES_LENGTH` (500).

## Task 5 — i18n keys
`Frontend/apps/storefront/src/i18n/he.ts`
- Every key from the gate-approved `copy.md`, copied verbatim from its approved column. `__tests__/i18n-keys.test.ts` scans `src/` for `"section.key"` literals and asserts each resolves to a non-empty Hebrew string, so a missed key is a red test rather than a blank `<span>`.
- **Seven keys beyond the spec's inventory**, each approved at the gate: `booking.continue` (forward label, steps 1–3 — the spec has one forward label for four actions), `booking.pickTime` (the slot grid's visible `<legend>`), `booking.forDress` (the item-path binding chip), `booking.confirmDress` (the confirmation's dress line), `booking.contactUnavailable` (the D12 no-boutique degrade), **`booking.sizeRequired`** (the item path cannot submit without a size — the backend rejects `dress_id` without `dress_size`) and **`errors.otpSendBudget`** (a `429` on `/otp/send` means roughly an hour's wait, which is different advice from `errors.tooManyAttempts`).
- The last two were caught only in review: the design renders them and the deck never defined them, so they would have been **failing tests on day one**, not blank spans.
- Delete the keys D1 makes dead (`booking.panelTitle`, `booking.close`) **only after** grepping for remaining uses — the i18n test checks used→defined, never defined→used, so nothing fails if they are left behind.

## Task 6 — `packages/ui`: `Checkbox`, `ButtonLink`, and the `ref` gate condition
`packages/ui/src/components/{Checkbox,Button,Input,TextArea,Select}.tsx`, `packages/ui/src/index.ts`, `packages/ui/src/__tests__/form-primitives.test.tsx`
- **`ref` on `Input` / `TextArea` / `Select`** — one line each (`ref?: Ref<HTMLInputElement>` etc., copying `Button.tsx:12`). **Do this first**: without it Tasks 9–11 cannot implement focus-to-first-invalid or `OTP_INVALID` focus retention, which are the flow's two WCAG 3.3.1 behaviours. This is the design gate's stated gate condition.
- `Checkbox` per the gate's §5 spec: real `<input type="checkbox">` with **no role override** (`Toggle` hardcodes `role="switch"`, which announces on/off where a legal consent must announce checked/unchecked), label required and visible, the `<label>` wrapping box + text at `min-block-size: 44px` with a 24×24 box, error via `aria-describedby` + `role="alert"`, `focusRing`.
- `ButtonLink` in `Button.tsx`, sharing `base`/`variants`/`sizes`/`focusRing`; no `loading`, no `disabled`, no `type`, no `ref`. `Button`'s own render must be **byte-identical** afterwards — assert it rather than trusting the edit.
- Seven files, so this task exceeds the ≤3 rule. It is one commit because the three `ref` lines, the two new components and the barrel export are one contract; splitting them ships a `packages/ui` that the app cannot consume.

## Task 7 — Router: the `/book` routes
`Frontend/apps/storefront/src/router.tsx`, `src/routes/BookPage.tsx` (stub), `src/__tests__/router.test.tsx`
- The six coordinated edits, all compiler-enforced: component import; `RouteName` gains `"book"`; `RouteMatch` gains `{name:"book", step, dressId?}`; `DOC_TITLE_KEYS` gains `book: "document.book"` (it is a `Record<RouteName,string>` and will not compile without it); the `matchRoute` if-chain; the render switch.
- Route shape `/book/{step}` and `/book/{step}/{dressId}` with `step ∈ {slot,details,terms,verify,confirm}` a **closed set**, so a step name can never be read as a dress id. Bare `/book` renders the slot step.
- **Amend the header comment** (`router.tsx:12-18`): "Swap in react-router when E3's booking flow needs nested layouts" is now void — `StorefrontLayout` mounts above the Router in `App.tsx`, so these routes nest for free and no dependency is added. Leaving the comment makes the file argue with the feature.
- **Do not add `book` to `hasBookingBar`** (`StorefrontLayout.tsx:63`). Its `catalog || dress` default correctly excludes `/book`; the inverse mistake would put a "book" CTA inside the booking flow. `A11yMenu` therefore gets `hasBookingBar={false}` there and rests at `--space-4`, not `--space-a11y-clearance`.
- One document title for the whole flow. A per-step title written from inside `BookPage` would be clobbered: React flushes child passive effects before the parent's, and the Router's title effect re-runs on every path change.

## Task 8 — Slot step  *(design-dependent — follows `booking.md` §3)*
`src/routes/BookPage.tsx`, `src/components/booking/TypePicker.tsx`, `src/components/booking/SlotPicker.tsx`
- Entry terms-check: `GET /storefront/terms` 404 ⇒ the phone-only entry (D5). **Branch on the 404 at this call site, before `errorMessageKey`** — `NOT_FOUND` means two different things on two different calls and the shared helper cannot discriminate.
- `TypePicker`: native `<fieldset>` + radios; duration; `audienceBrides` badge (D10, labels not gates); the **per-row** deposit branch (D3) — a deposit row reveals its phone-only note + `ContactPanel` while a non-deposit sibling stays bookable.
- `SlotPicker`: native date input + chip grid, radio semantics, `<bdi dir="ltr">` on every time. **`repeat(auto-fill, minmax(104px, 1fr))` with `gap: var(--space-2)` yields 2 columns at 375 and 5 at ≥768** (R10) — the arithmetic is in the ruling; do not "fix" it to 3-up without redoing it.
- **Card padding is `var(--space-6)` at every width, 375 included** (R9). `Card` hardcodes `p-6` and `cn` has no tailwind-merge, so a caller's `p-4` ships both classes and loses on stylesheet order. Four design sections specified `--space-4` at 375; all four are struck. If 16px is genuinely wanted it is a `packages/ui` change, not a className.
- **The forward button is never `disabled`** (R7) — pressing it with nothing chosen renders inline `role="alert"` messages and moves focus to the first unfilled group. Do not carry `aria-describedby` on a disabled control; it is inert because `disabled` drops the control from the tab order.
- States: loading (**with a `VisuallyHidden role="status"`** — `aria-busy` on a plain div is announced by neither VoiceOver nor NVDA, R30), `noTypes`, `noSlots`, `slotsError`, `SLOT_UNAVAILABLE` return, `typeGoneRepick` return, `TOO_MANY_ATTEMPTS`.

## Task 9 — Details + terms steps  *(design-dependent — §4, §5)*
`src/routes/BookPage.tsx`, `src/components/booking/SizeChips.tsx`, `src/__tests__/BookPage.test.tsx`
- Name + notes with the Task 4 validators; size chips on the item-based path (P2), out-of-stock **selectable** (D4) and styled as an invitation, never as a warning badge.
- **`dress_size` is REQUIRED whenever `dress_id` is sent — the spec's contract table is wrong.** It writes the body as `{… dress_id?, dress_size?, notes?}`, which reads as three independently optional fields; `Backend/app/booking/validation.py` enforces the two-path model at the boundary (`dress_id` without a non-blank `dress_size` is a `400`, and `dress_size` without `dress_id` is a `400`). So on the item path a size is not optional decoration — the forward control must not advance without one. Amend the spec's table in the same PR.
- Length checks run on the **raw** value, the blank check on the **trimmed** value, and the value sent on the wire is the **raw** one — mirroring `validation.py` line for line. A client that validates a different string than the server receives is how a `400 VALIDATION_ERROR` the client believed impossible reaches a bride.
- Errors surface on **submit**, never on blur, never on input; the forward button is **never disabled on validation state** — it submits and fails visibly, because `disabled` states no reason and drops the control out of the tab order.
- Terms: the two refund numbers in plain Hebrew above the policy text; policy rendered as **text, never HTML**; `Checkbox` consent.
- Step guards: a later step entered with no picked slot returns to `slot`. `confirm` is exempt.
- `TERMS_STALE` return re-shows the new text and **resets the checkbox**.

## Task 10 — Verify, submit, confirm  *(design-dependent — §6, §7)*
`src/routes/BookPage.tsx`, `src/__tests__/BookPage.test.tsx`
- OTP send/verify; resend cooldown 60s with **no ticking number** (R3 — i18next cannot carry the `<bdi>` a numeral needs, and Hebrew's dual form has no plural resources configured); the verification token held **in memory only** — `qa-greps.sh` bans `localStorage` and the 600s TTL cannot survive a reload anyway.
- Submit → `201` → `confirm`. Confirm renders the full record from the payload; **cold** confirm renders the short booked state over `ContactPanel` and never bounces to step one.
- `verify` reached with a spent token but a completed booking forwards to `confirm`.
- **The submit can fail outside the designed set — 429, 5xx, dropped connection — and that state is mandatory (R13).** Re-enable the submit button, render `errors.unknown` in the step-level muted `role="alert"`, and show `ContactPanel` beneath it. Retry is safe because the backend rolls the whole transaction back, so the token survives. Without this row a bride who verified, accepted the policy and pressed commit gets a spinner that stops and **no way to learn whether she is booked** — the exact failure this feature exists to remove.
- **The cold confirmation must not assert a booking it cannot verify (R14).** `booking.confirmTitle` is warm-branch only; the cold branch takes a neutral heading and conditional copy. `/book/confirm` is guard-exempt, so a hand-typed URL or a stale bookmark reaches it with no payload.

## Task 11 — The error-recovery matrix  *(design-dependent)*
`src/routes/BookPage.tsx`, `src/__tests__/BookPage.test.tsx`
- `SLOT_UNAVAILABLE` ⇒ re-fetch slots and re-pick. `TERMS_STALE` ⇒ re-show and re-accept. `PHONE_NOT_VERIFIED` ⇒ restart verification, **preserving slot, name, notes and terms acceptance**.
- **The submit-time `NOT_FOUND` probe**: one code, three causes, no discriminator. Re-fetch `/appointment-types` and, if bound, `/dresses/{id}`. Type missing ⇒ `typeGoneRepick` back to the picker; both present ⇒ the size variant went, return to the size chips. **Dress missing ⇒ drop the binding in memory and re-issue the booking POST once**, landing on `confirm` with `booking.dressGoneGeneric` shown there (R20) — the spec's words are "drop the binding and *continue*", and walking her back two steps for a decoration she did not choose costs three navigations against a partly-spent 600-second token.
- **The probe has its own in-flight and failure states (R20)**: the submit button **stays `loading`** while the probe's one or two GETs run, and if the probe itself 429s or 5xxs — realistic, since every read shares the per-tenant throttle — render `errors.unknown` in the step-level block and **leave her on `verify` with everything intact**. The probe was named in three places in the spec and designed in none.
- `SMS_*` ⇒ an honest dead end with a contactable exit, not a spinner.
- All three `ContactPanel` branches degrade to plain copy when `useBoutique()` has nothing (D12).

## Task 12 — The CTA flip (D1 + D12) — **atomically 7 files**
`src/components/BookingCTAButton.tsx`, `src/routes/{CatalogPage,DressPage,AboutPage}.tsx`, `src/__tests__/{AboutPage,CatalogPage,DressPage}.test.tsx`
- `<Link to="/book/slot" className={buttonClasses()}>` (P1); the dress page carries `/book/slot/{dressId}` (D9 — a path segment; the navigation store snapshots `pathname` only and cannot see a query string).
- Drop the now-dead `boutique` prop and the `Modal`/`ContactPanel` import; amend the docstring, which currently says the panel "is the SHIPPED v1 behaviour, not a placeholder".
- Remove `/catalog`'s boutique-fetch guard (D12) — a button that navigates needs no boutique data.
- **Why one commit and not three**: removing a required prop does not compile piecemeal. Stated rather than pretending the ≤3-file rule holds.
- New assertions, per Risk 3 **plus the role change**: `AboutPage` — the CTA is a link to the booking route and opens **no** dialog; `DressPage` — on a reserved dress it renders and its `href` carries the dress id; `CatalogPage` — the CTA now renders **even when the boutique fetch fails**. `inline` stays (it is `/about`'s no-fixed-bar requirement).
- **Two of the four assertions go VACUOUS rather than red, and must be rewritten deliberately.** `AboutPage.test.tsx:282,295` and `CatalogPage.test.tsx:152` hard-fail once the role changes `button` → `link`, which is safe. But `CatalogPage.test.tsx:183` is `expect(queryByRole("button", …)).toBeNull()` — trivially true once the CTA is a link, so **the exact assertion D12 inverts would go silently unverified**; and `DressPage.test.tsx:254`'s `toBeEnabled()` is a no-op on an `<a>` (jest-dom's disabled matchers apply only to `button/input/select/textarea/optgroup/option/fieldset`). Both must be re-pointed at `role="link"` and at the `href`. A green suite here does **not** mean the two behaviours are covered.

## Task 13 — E2E + mechanical
`Frontend/e2e/storefront.spec.ts`
- Booking fixtures; axe per new route with `withTags(["wcag2a","wcag2aa"])`; no horizontal scroll at 375/768/1440; skip link first Tab stop; reduced motion.
- The two booking pins: `/book/*` renders **no** `BookingCTA` bar at 375 (Risk 6 asserted, not assumed), and the **browser back button walks the steps in reverse** rather than leaving the flow (D8).
- `qa-greps.sh` clean.

## Task 14 — Review + ship
- Full suites both sides. Dual review: `phase-reviewer` + adversarial (token replay from the UI, phone-normalisation drift across the three calls, error-copy misrouting, the `isNotFound` trap, cross-tenant).
- Epic row F14 → done; PR `Feature 14: Storefront booking UI (Epic E3)`; watch `gh pr checks`; merge.

## Testing plan → spec criteria

- **Every "unit" row of the spec's State matrix gets a case** in `BookPage.test.tsx`, modelled on `CatalogPage.test.tsx`: `vi.mock("../api")` spreading `importActual` so `ApiError`/`errorMessage*` keep real behaviour, render inside the real `StorefrontLayout`, assert against real Hebrew from `i18n`.
- **The three assertions the spec names as easy to write vacuously**: a booking-path `400 VALIDATION_ERROR` must **not** render "השמלה כבר לא זמינה"; the `name` and `notes` bounds are tested at the boundary — 500 submits and 501 is refused client-side **with no request issued**, likewise 80 and 81; and a `deposit_required` type renders the phone-only branch **while a non-deposit sibling in the same picker stays bookable**.
- Backend: the house treatment in Task 2.
- `BookPage.test.tsx` may split by step if it passes ~600 lines — one file is the `CatalogPage` precedent, not a rule.

## Commit sequence
1. `docs(planning): F14 design gate + implementation plan (Gate 2)`
2. `feat(storefront): public terms endpoint for anonymous booking`
3. `feat(storefront): mutation-capable apiFetch and booking error copy`
4. `feat(storefront): client validation with backend constant parity`
5. `feat(ui): checkbox primitive and button class recipe`
6. `feat(storefront): /book routes`
7. `feat(storefront): slot step`
8. `feat(storefront): details and terms steps`
9. `feat(storefront): phone verification, submit and confirmation`
10. `feat(storefront): booking error recovery`
11. `feat(storefront): CTA navigates to the booking flow`
12. `test(e2e): booking flow coverage`
13. review fixes, then PR.
