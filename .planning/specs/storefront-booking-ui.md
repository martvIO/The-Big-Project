# Spec: Feature 14 — Storefront Booking UI (Epic E3)

**Created**: 2026-07-29 · **Revised**: 2026-07-29 (rev 2 — Gate 1 held, post-verification pass) · **Status**: Gate 1 approved 2026-07-29 (**D1–D7**; **D8–D9** confirmed with the user post-gate, **D10–D12** record decisions the code had already forced) — **not yet build-ready**: the design gate and the implementation plan are both outstanding, see §Dependencies · **Epic**: E3 Feature 14 · **Effort**: L (revised up from M at Gate 1 for the backend amendment; the `packages/ui` split rule in §Design is what could move it again, and `openapi-typescript` adoption is scoped out to keep it honest)
**Depends on**: E3 #13 (the booking API), #12 (slots + appointment types), #11 (OTP send/verify), E2 #10 (the storefront app and its CTA seam), #9 (`packages/ui`) · **Feeds**: #16 (comms lifecycle sends against bookings created here), E4 (deposit redirect inserts into this flow)

> **Gate 1 was held on 2026-07-29; all seven open questions are answered in
> §Decisions Log as D1–D7.** A verification pass then re-read the shipped code behind
> each answer and found **six** statements this draft had wrong — the `notes` sanitising
> rule and its 500-vs-2000 bound, the 404 envelope, the reach of the storefront's
> error-code mapping, the premise that a route needs react-router, the claim that
> `StorefrontLayout` owns focus management, and where `GET /storefront/terms` must live
> and what it inherits. Each correction is marked **rev 2** where it lands. That pass
> also surfaced two questions D1–D7 had left implicit; they went back to the user and
> returned as **D8** and **D9**. **D10–D12** record decisions the shipped code had
> already made or forced — including **D12**, which inverts a reasoned F10 behaviour and
> changes a shared component's props across three call sites, so it is not a footnote.
> Line references are against the working tree at `5f2e58d`, and the files this feature
> modifies will move them.

## Problem

F13 shipped the endpoint that writes a booking. Nothing calls it. The storefront's
"קביעת תור" button has been live since F10, and it opens a contact panel — a real,
shipped fallback that tells the bride to phone the boutique. Every booking the pilot
takes today is still a phone call someone has to answer.

This is also the feature where the product's whole promise gets tested by a real
person: a bride on a phone, in Hebrew, right-to-left, who has to pick a time, prove
her number over SMS, read a cancellation policy and commit — without a single dead end
that leaves her not knowing whether she has an appointment.

## Scope correction — this is not a UI-only feature

The epic brief described F14 as "the customer-facing flow ... on the storefront",
implying frontend only, until this spec — it now records the amendment below. F14 cannot
be built frontend-only, for a reason no earlier feature surfaced:

**`POST /storefront/bookings` requires `terms_version`, and there is no public way to
learn it.** Terms live at `GET /manage/terms`, behind owner authentication. An
anonymous bride can neither discover the current version number to send nor read the
policy text she is being asked to accept. F13 rejects a stale or absent version with
`409 TERMS_STALE`, so without a public endpoint the flow cannot succeed even once.

F14 therefore carries a backend amendment. This follows F10's precedent exactly — that
spec has a section titled "The F7 profile amendment (delivered here, deliberately)" for
the same shape of problem — and the effort estimate moves M → L to match.

### The terms amendment (delivered here, deliberately)

`GET /storefront/terms` on the existing GET-only public router
(`backend/app/storefront/router.py`), anonymous, tenant-from-Host, `no-store` like
every sibling.

```json
{ "version": 3, "terms_text": "…", "refundable_until_hours_before": 48, "forfeit_percent": 50 }
```

**A strict field allowlist, per F10's "what the storefront must never see" rule.**
`TermsVersion` also carries `id`, `tenant_id`, `created_by` (the owner's staff UUID)
and the standard timestamps. None of those reach the anonymous wire; `created_by`
especially is an internal principal identifier with no business on a public surface.
The response object is built field-by-field, never by serialising the row.

**It gets its own narrow schema — it may not reuse or subclass
`TermsVersionResponse`** (`backend/app/boutique/schemas.py:157-166`), which carries
`created_by` and is the element type of the owner-only paginated history.
`backend/app/storefront/schemas.py`'s module docstring forbids subclassing a manage
schema outright ("None of these subclass a manage schema, and none ever may"), and a
test asserts the non-inheritance.

`refundable_until_hours_before` and `forfeit_percent` ship alongside the text because
they are the two numbers a bride is actually agreeing to, and the UI should state them
in plain Hebrew rather than making her infer them from a paragraph.

**rev 2 — where it goes and what it inherits.** It belongs on
`backend/app/storefront/router.py` itself, not a sibling router: the sibling-router
pattern exists only because that router is contractually GET-only, and a read is a GET.
Being on it means inheriting both router-level dependencies — `_no_store` **and
`_throttle`**, so the call spends the per-tenant read budget, which
`test_the_read_throttle_is_not_inert` will prove. Registering it requires exactly one
hand-written line: `"/storefront/terms"` added to the literal path set in
`backend/tests/test_storefront_api.py:529-545` (the cross-router shadowing guard is
deliberately hand-maintained so "adding a public surface must fail one test on
purpose"). Everything else arms itself — the guard suite derives its route list from the
live table, so the new endpoint is automatically swept into the no-auth, no-cache,
tenant-not-exempt, no-manage-field-leak and throttle checks.

**A boutique with no terms cannot take bookings** — F13 already enforces this, and the
manage console already treats it as a blocking banner ("אין מדיניות ביטולים",
`.planning/design/ideation/flows.md:43`). **D5** settles what this endpoint answers in
that state.

## Goal

A bride reaches the storefront from an Instagram link, taps "קביעת תור", picks a real
bookable time, gives her name, accepts the versioned policy, verifies her phone with a
one-shot code, and lands on a confirmation screen naming her appointment — in Hebrew
RTL, on a 375px screen, passing axe at WCAG 2.0 AA. (That order is D2, and it is load-
bearing: the code is minted last so the 600-second token cannot die while she reads the
policy.) Both paths work: from a dress page the booking carries that dress and size;
from the catalog or About it is a generic appointment.

Every failure the API can return has a designed recovery that keeps her in the flow —
in particular the two that happen to real people at real boutiques: the slot was taken
while she was typing, and the owner republished the terms mid-session.

## The contract F14 consumes (all shipped, verified against code)

Wire format is the backend's `snake_case` **verbatim** — the storefront does no case
conversion, and its TypeScript interfaces mirror the Python schemas field-for-field.
(`frontend/apps/storefront/src/api.ts` is the existing precedent; the `keysToSnake`
convention in `.claude/rules/` belongs to a different stack and does not apply here.)

| Call | Shape |
|---|---|
| `GET /storefront/appointment-types` | a **bare list** (no envelope, unlike `/dresses` and `/slots`): `[{id, name, duration_minutes, audience, deposit_required, deposit_amount_agorot}]` |
| `GET /storefront/dresses/{dress_id}` | the item-based path's source for the dress name and the size chips — `sizes[].available` is `quantity > 0` and per **D4** does not gate selection. Archived or unknown ⇒ `404 NOT_FOUND`, which on `/book/…/{dressId}` drops the binding and continues as a generic appointment rather than dead-ending |
| `GET /storefront/slots?from=&to=` | `{slots: [{starts_at}]}` — bare instants; capacity is deliberately never on the wire. `from` defaults to today in Jerusalem, `to` to +14d, clamped to 60d; `to < from` is a 400 |
| `GET /storefront/terms` | **new, this feature** |
| `POST /storefront/otp/send` | `{phone}` → `204`. Always 204 — never reveals whether a code went out |
| `POST /storefront/otp/verify` | `{phone, code}` → `{verification_token, expires_at}` |
| `POST /storefront/bookings` | `{phone, verification_token, name, appointment_type_id, starts_at, terms_version, (dress_id + dress_size)?, notes?}` → `201 {id, starts_at, status, appointment_type_name, dress_name, dress_size}`. **`dress_id` and `dress_size` are a PAIRED optional, not two independent ones**: `backend/app/booking/validation.py` enforces the two-path model — item-based carries both, generic carries neither, and a `dress_id` whose `dress_size` is absent or blank (or a `dress_size` with no `dress_id`) is a `400 VALIDATION_ERROR`. Consequences the UI inherits: the size control is **required** on the item-based path, there can be no "not sure" option, and a bound dress with no pickable size must drop the binding rather than send half a pair |

**Error codes the UI must map to Hebrew copy** (the house helper selects copy by
`code`, never by the server's message — every backend message is English):

| Code | Status | Meaning for the bride |
|---|---|---|
| `OTP_INVALID` / `OTP_EXPIRED` | 400 | wrong or stale code — retry inline |
| `PHONE_NOT_VERIFIED` | 403 | the token died (600s TTL) or was already spent — restart verification |
| `SLOT_UNAVAILABLE` | 409 | taken, off-grid, past, or beyond the published window — **re-fetch slots and re-pick** |
| `TERMS_STALE` | 409 | policy changed mid-session — **re-show and re-accept** |
| `NOT_FOUND` | 404 | **two meanings, told apart by call site, never by code**: on `/bookings` or `/dresses/{id}` the dress or appointment type was archived mid-session; on `GET /storefront/terms` the boutique has no published policy (**D5**) — degrade to `ContactPanel`, never an error toast. `errorMessageKey` cannot discriminate, so the terms call branches on the 404 before it reaches the shared helper |
| `TOO_MANY_ATTEMPTS` | 429 | per-phone or per-tenant budget spent |
| `SMS_NOT_CONFIGURED` / `SMS_UNAVAILABLE` | 503 | phone verification is down — the flow cannot complete; say so honestly |
| `VALIDATION_ERROR` | 400 | shape violation; should be unreachable if client validation mirrors the server |

**rev 2 — the mapping is partial, and there are two 404s.** `errorMessageKey`
(`frontend/apps/storefront/src/api.ts:44-58`) maps exactly four codes today —
`TENANT_NOT_FOUND`, `NOT_FOUND`, `TOO_MANY_ATTEMPTS`, `VALIDATION_ERROR`. **Seven of the
ten codes in the table above fall through `default:` to `errors.unknown`** and render
the generic Hebrew apology: `OTP_INVALID`, `OTP_EXPIRED`, `PHONE_NOT_VERIFIED`,
`SLOT_UNAVAILABLE`, `TERMS_STALE`, `SMS_NOT_CONFIGURED`, `SMS_UNAVAILABLE`. Each needs a
`switch` case, and the seven share **six** new `i18n/he.ts` keys — the two `SMS_*` codes
map to one — which is net-new work, not wiring. **The other three are already mapped and
already carry Hebrew; do not add a
second case or a second key for them** — but their existing copy is dress-shaped
(`NOT_FOUND` renders "השמלה כבר לא זמינה"), so the booking and terms calls must not
reuse it. Two further traps: the helper returns
an **i18n key**, not Hebrew (Hebrew materialises only when a `t` is passed, via
`errorMessage`/`errorMessageOr`); and `isNotFound` (`api.ts:33-36`) counts
`400 VALIDATION_ERROR` as "dress not found" — reusing it on a booking call would show
"השמלה כבר לא זמינה" for a mistyped phone number. Separately, an unresolvable Host
returns `TENANT_NOT_FOUND`, not `NOT_FOUND`; they are different envelopes and
`test_storefront_paths_are_not_exempt` asserts the distinction.

**The verification token's 600-second TTL is the flow's hard constraint.** It is minted
at `/otp/verify` and burned by `POST /bookings`. Everything between those two calls has
to fit inside ten minutes, which is what makes step ordering a correctness question
rather than a taste one — **D2** settles it.

## What already exists to build on

- **The seam.** `frontend/apps/storefront/src/components/BookingCTAButton.tsx` is
  documented as "The E3 seam", with "E3 #14 replaces the panel's contents behind the
  same button". The button, its keyboard reachability and the fixed-bar footprint are
  shipped and QA'd. **D1 supersedes that sentence** — the button navigates rather than
  opening the panel — so the docstring is amended by this feature, and it must not be
  described as replacing a stub: the same docstring says today's behaviour "is the
  SHIPPED v1 behaviour, not a placeholder to be improved".
- **The contact panel is reusable; the modal composition is not.** `ContactPanel`
  (`frontend/packages/ui/src/components/ContactPanel.tsx`) is an exported shared
  component with two existing call sites, and `ContactCard` already wraps it in a `Card`
  with `safeHref` applied and a null-return when every channel is empty. The
  button+Modal+title+close assembly is inline JSX inside `BookingCTAButton` with only
  `boutique` and `inline` props — a new screen reuses the *panel*, not the modal. What
  neither provides is explanatory prose; D3 and D5 both need new `booking.*` keys for
  the sentence above the panel. (Note `BookingCTAButton` has no empty-state guard —
  `ContactCard` does; on `/dress` with a failed boutique fetch its modal opens empty.)
- **`packages/api-client`'s OWNER note claims this feature — and §Design declines it.**
  Its entire body is `export {}` plus a comment naming **"OWNER: E3 #14"**, on the
  reasoning that the booking flow adds the first real request bodies and that hoisting
  the duplicated fetch helpers out of `apps/manage` and `apps/storefront` belongs in the
  same pass. Both are deferred here; the note stays for whoever takes it.
  `openapi-typescript` is a devDependency with a `generate` script, but the
  script is not a working one-liner: it needs a live backend **and `APP_ENV=dev`**,
  because F10 gated `/openapi.json` out of non-dev environments. Nothing imports the
  package today and `src/generated/` does not exist.
- **`apiFetch` is GET-only — physically.** Its signature is
  `apiFetch<T>(path: string)`, one parameter; `frontend/apps/storefront/src/api.ts`
  cannot carry a body at all, so booking mutations change that signature rather than
  appending entries to the `api` object. `frontend/apps/manage/src/api.ts` is the
  mutation-capable precedent — same `ApiError`/`extractError` shape, plus
  `{method, body}` — but the two helpers are not interchangeable (manage sends
  `credentials: "include"` and surfaces the raw English backend message; the storefront
  omits credentials and maps codes to i18n keys). The storefront must keep
  `credentials: "omit"`: it is an explicitly reasoned decision in the file, the booking
  route is cookie-blind by contract, and a test asserts an owner cookie changes nothing.
  The verification token therefore travels in the request body, never a cookie.
- **i18n.** `frontend/apps/storefront/src/i18n/he.ts` already has a `booking` section
  (`cta`, `panelTitle`, `close`). Every visible string must live there — no component
  may hardcode Hebrew — and `__tests__/i18n-keys.test.ts` statically enforces it for
  any new `booking.*` key automatically.
- **Layout.** `StorefrontLayout` owns the single app-wide boutique fetch (and the
  `useBoutique()` context every route reads), the skip link, the `<main id="content"
  tabIndex={-1}>` focus *target*, the fixed-bar clearance, the footer and the
  `A11yMenu`. **rev 2 — it does not own focus management**: the focus move, the scroll
  reset and the `document.title` write all live in one effect in `router.tsx:196-211`,
  keyed on a `handledPath` ref so first paint never steals focus from the skip link.
  `DressPage`'s title override works only because it fires in a *later* commit, after
  its fetch resolves; a synchronous per-step title written from inside the booking page
  would be clobbered by the Router's own effect. See §Design.
- **The router is hand-rolled, and D1 lands inside its stated ceiling.** A `RouteName`
  string union, a `RouteMatch` discriminated union, a `Record<RouteName, string>` of
  title keys, an if-chain in `matchRoute`, and a render switch — adding `book` is **six**
  coordinated edits in `router.tsx` (the component import, `RouteName`, `RouteMatch`,
  `DOC_TITLE_KEYS`, the `matchRoute` if-chain, the render switch) plus a `document.book`
  i18n key, all mechanical and all compiler-enforced (`DOC_TITLE_KEYS` is a
  `Record<RouteName, string>` and will not compile without the entry). **The header
  comment's "swap in react-router when E3's booking flow needs nested layouts" does not
  apply**: `StorefrontLayout` is already mounted *above* the Router app-wide in
  `App.tsx`, so the booking routes nest in the same shell for free. Three shipped
  properties constrain the flow's navigation: `navigate()` is the only primitive and
  there is **no `back()` of any kind** — `qa-checklist.md:115` bans
  `history.back()`/`navigate(-1)`/`router.back()` for the dress-detail back-link and
  `router.tsx:17-18` generalises the ban to the whole app ("with no back() to call, the
  qa-checklist ban on history-based back navigation is structural rather than a grep"),
  because the storefront's primary entry is an Instagram-bio deep link with no history
  stack. Note what that does and does not forbid: the app may never *call* back, but the
  browser's own back button works — `popstate` is subscribed — which is what makes
  **D8**'s per-step URLs deliver real back semantics. Third, there is **no 404 route**:
  anything unmatched silently renders the catalog, so a mis-cased `/Book` fails as a
  dead end rather than an error.

### What `packages/ui` does not have

Every one of these is needed by a booking flow and absent today, so each is either a
new component in `packages/ui` or a deliberate one-off in the app:

stepper / progress indicator · radio group · **checkbox** (needed for terms acceptance —
note the near-miss: `Toggle` *is* a native `<input type="checkbox">` but hardcodes
`role="switch"` with no opt-out, which is the wrong semantic for a one-shot legal
consent, so a checkbox-role primitive is genuinely absent) · chip or segmented control ·
any date picker or calendar (only native `<input type=date>`) · slot grid · OTP code
input · phone input forced LTR · form/fieldset wrapper · form-level error summary ·
client validation utilities (`apps/manage/src/validation.ts` is the precedent: pure
functions returning a Hebrew string or `null`).

Three existing constraints will bite:

1. **`Modal` is fixed-width (`w-[min(28rem,…)]`) with no scroll handling and no size
   variants.** A multi-step form with a slot grid and a policy text does not fit it as
   built. This was the strongest argument that carried **D1** to a route.
2. **`cn` has no tailwind-merge**, so caller classNames cannot reliably override a
   component's base classes — which rule wins is decided by stylesheet order.
   `BookingCTAButton` documents being bitten by exactly this.
3. **Toast is one-at-a-time with no queue**, 4s auto-dismiss. It cannot carry anything
   the bride must read, and must not be the only report of a failure.

## The flow, as decided

Gate 1 answered all seven of the draft's open questions. A verification pass then put
two more to the user (**D8**, **D9**) and recorded one the backend had already made
(**D10**); a second pass found a hole none of them covered and closed it as **D11**, and
recorded the CTA's now-obsolete boutique guard as **D12**. They survive here only in
§Decisions Log, with their reasoning. The shape they add up to:

**Booking is a route, and every step owns a URL.** The storefront CTA navigates instead
of opening the contact panel. The stepper is **four steps — slot → details (name,
optional `notes`) → terms acceptance → OTP** — and submitting from the fourth lands on
`confirm`, a terminal screen outside the stepper (which is why there is no
`stepConfirm` label). The 600-second verification token is minted last
and cannot expire while she reads a cancellation policy. Each step is its own path
(**D8**), so the browser's back button walks the steps rather than dumping her out of
the flow; the in-app back control is a `<Link>` to the previous step, never a history
pop. The item-based path carries the dress as a **path segment** (**D9**) — the
hand-rolled navigation store cannot see a query string.

**The appointment type is chosen at the top of the slot step** (**D11**), not in a step
of its own: `POST /storefront/bookings` requires `appointment_type_id`, and slots are
type-independent on the wire, so she picks *what* and then *when* on one screen. That
screen is where D3's deposit branch and D10's brides-only badge live.

**Two paths degrade to contact-by-phone rather than to a broken form**: the entry
itself, when a boutique has no published terms (`GET /storefront/terms` →
`404 NOT_FOUND`); and, inside the flow at the type picker, any appointment type with
`deposit_required` — visible, labelled, but not bookable online until E4 wires payment.
Both render `ContactPanel` under a sentence of new Hebrew copy explaining why.

**A size that is out of stock stays selectable** (**D4**), under copy telling her it may
need to be ordered in — a fitting is not a purchase, and F13 validates only that the
variant exists and is active. **A brides-only appointment type is labelled, not gated**
(**D10**), which is what the shipped backend already assumes.

**The confirmation screen promises no SMS**, because F16 has not shipped and a booking
created here sends nothing. It is the only confirmation that exists, so it states the
appointment in full and tells her to screenshot or save it.

## Design

### Backend — the terms endpoint

| File | Action | Responsibility |
|---|---|---|
| `backend/app/storefront/router.py` | modify | `GET /storefront/terms` on the existing GET-only router, inheriting `_no_store` + `_throttle` |
| `backend/app/storefront/schemas.py` | modify | a new narrow public model — **not** a subclass of `TermsVersionResponse`; exactly `{version, terms_text, refundable_until_hours_before, forfeit_percent}` |
| `backend/app/storefront/service.py` | modify | current-version read; absent ⇒ the `NOT_FOUND` path |
| `backend/tests/test_storefront_api.py` | modify | add `"/storefront/terms"` to the hand-maintained literal path set (this is what arms the five derived guard suites) |
| `backend/tests/test_frontend_constant_parity.py` | modify | generalise to read both `validation.ts` files; add the two rows named in **D7** |

### Frontend (paths are under `frontend/apps/storefront` unless rooted)

| File | Action | Responsibility |
|---|---|---|
| `src/router.tsx` | modify | the six edits above. `RouteName` gains **one** member, `book`; `RouteMatch` gains `{name:"book", step, dressId?}`. Route shape: `/book/{step}` and `/book/{step}/{dressId}`, where `step ∈ {slot, details, terms, verify, confirm}` is a closed set — so a step name can never be mistaken for a dress id. Bare `/book` renders the slot step. **One `DOC_TITLE_KEYS` entry and one title for the whole flow**: a per-step title written from inside `BookPage` would be clobbered, because React flushes child passive effects before the parent's and the Router's title effect re-runs on every path change. If per-step titles are wanted later, the Router effect must be the thing that reads `match.step` |
| `src/routes/BookPage.tsx` | new | the step machine, all states, and the prerequisite guards — a later step entered directly with no picked slot or no live token sends her back to `slot` rather than rendering a form that cannot submit. **`confirm` is exempt from that guard**: the booking is already written, so it renders from the `201` payload held in memory; `verify` reached with a spent token but a completed booking forwards to `confirm` instead of `slot`; and `confirm` loaded cold (a reload, or the screenshot round-trip on iOS) shows a short "your appointment is booked" state over `ContactPanel` rather than bouncing her to step one — there is no public endpoint to re-read a booking by id |
| `src/components/BookingCTAButton.tsx` | modify | navigates instead of opening the modal; docstring amended; the now-dead `boutique` prop removed (**D12**) |
| `src/api.ts` | modify | `apiFetch` gains `{method, body}` while keeping `credentials: "omit"`; `errorMessageKey` gains seven cases; new calls for terms / appointment-types / slots / dress detail / otp send+verify / bookings |
| `src/validation.ts` | new | `validateName` (80), `validateNotes` (500) and `validatePhone` as pure functions returning a Hebrew string or `null`, per the `apps/manage` precedent. Phone normalisation happens **once**, here, before any of the three calls that carry it — a client that normalises differently across `/otp/send`, `/otp/verify` and `/bookings` produces `PHONE_NOT_VERIFIED` for a correct code |
| `src/i18n/he.ts` | modify | every new key below |
| `src/__tests__/BookPage.test.tsx` | new | the step machine and every state in the matrix below |
| `src/__tests__/{AboutPage,CatalogPage,DressPage}.test.tsx` | modify | the CTA assertions **D1** inverts (navigate, not dialog) and, on `CatalogPage` only, the one **D12** inverts |
| `frontend/e2e/storefront.spec.ts` | modify | booking fixtures, an axe pass per new route, and the two booking-specific pins in §Testing |
| `frontend/packages/ui` | modify | the primitives from §What `packages/ui` does not have. **The split rule**: anything a second app would plausibly need — checkbox, radio group, form/fieldset wrapper, error summary, stepper — goes in `packages/ui` and inherits its design-gate obligation; anything shaped by this one flow — slot grid, OTP input, phone input, size chip behaviour — stays app-local; the date picker is neither, because the native `<input type=date>` is the answer. The plan applies that rule item by item and sizes it; it is the largest unknown in the estimate |

**i18n inventory.** `document.book` · `booking.{stepSlot, stepDetails, stepTerms,
stepOtp, stepsLabel, typeHeading, typeDuration, pickDate, noSlots, noTypes, slotsError,
phone, phoneHint, phoneInvalid, name, nameRequired, nameTooLong, notes, notesHint,
notesTooLong, sizeUnavailable, audienceBrides, termsHeading, refundWindow, forfeit,
acceptTerms, acceptRequired, otpSent, otpCode, otpResend, otpResendWait, submit,
submitting, backStep, depositByPhone, noTermsByPhone, typeGoneRepick, dressGoneGeneric,
sizeGoneRepick, confirmTitle, confirmKeepScreen, confirmWhen, confirmWhat, confirmCold,
backToCatalog}` ·
`errors.{otpInvalid, otpExpired, phoneNotVerified, slotUnavailable, termsStale,
smsUnavailable}` — **six keys for seven `switch` cases**: `SMS_NOT_CONFIGURED` and
`SMS_UNAVAILABLE` deliberately share `errors.smsUnavailable`, because the difference
between them is the boutique's problem and not the bride's.
`__tests__/i18n-keys.test.ts` enforces every one automatically. This list is the
checklist Risk 5 asks for; the design gate owns the actual Hebrew.

**Deliberately not here: `packages/api-client`.** The OWNER note assigns codegen
adoption and the fetch-helper hoist to F14, and this spec **defers both** (Risk 4). The
flow ships against `src/api.ts`; adopting `openapi-typescript` and hoisting helpers out
of two apps is a refactor with its own blast radius and its own PR, and bundling it here
is what would make the estimate indefensible. The OWNER comment stays where it is.

## State matrix

**This table is the single source for states.** The design gate designs every row marked
D, the test suites cover every row, and nothing else in this spec re-enumerates them.

| State | Trigger | Design | Test |
|---|---|---|---|
| Happy path, generic | — | D | unit + e2e |
| Happy path, item-based | entered from a dress page | D | unit + e2e |
| Loading | any fetch in flight | D | unit |
| No published terms → phone-only entry | `GET /terms` → `404` (**D5**) | D | unit |
| No active appointment types | empty list from `/appointment-types` | D | unit |
| Deposit-required type → phone-only | `deposit_required` (**D3**) | D | unit |
| Brides-only badge | `audience` (**D10**) | D | unit |
| Out-of-stock size selectable | `available: false` (**D4**) | D | unit |
| No bookable times in the window | empty `slots` — the state every new tenant ships in | D | unit |
| Slot taken while she typed | `SLOT_UNAVAILABLE` → re-fetch and re-pick | D | unit + e2e |
| Terms republished mid-session | `TERMS_STALE` → re-show and re-accept | D | unit + e2e |
| Something vanished mid-session | `NOT_FOUND` on submit — **one code, three causes, no discriminator** (see below) | D | unit |
| Dress archived before the flow | `NOT_FOUND` on the dress read → drop the binding, continue generic | D | unit |
| Token expired / spent | `PHONE_NOT_VERIFIED` → restart verification | D | unit |
| Wrong or stale code | `OTP_INVALID` / `OTP_EXPIRED` → retry inline | D | unit |
| OTP resend before cooldown | client-side timer; `/otp/send` always answers `204` and reveals nothing | D | unit |
| Verification unavailable | `SMS_*` → honest dead end, the flow cannot complete | D | unit |
| Rate limited | `TOO_MANY_ATTEMPTS` | D | unit |
| Client validation failures | name > 80, notes > 500, bad phone, terms unchecked | D | unit |
| Confirmation | `201` (**D6** — no SMS promise) | D | unit + e2e |
| Confirmation loaded cold | reload or app-switch after submit; no public read-by-id exists | D | unit |
| Step entered without prerequisites | guard → `slot` (**D8**) | — | unit |
| Browser back across steps | `popstate` (**D8**) | — | e2e |
| Boutique fetch failed → no contact fallback | `useBoutique()` has nothing, so every `ContactPanel` branch would render an empty box (**D12**, gate proposal **P8**) → plain copy via `booking.contactUnavailable` | D | unit |
| Submit failed outside the designed set | `429` / `5xx` / dropped connection on `POST /bookings` (**R13**) → re-enable submit, `errors.unknown`, contactable exit. **The flow's true terminal dead end before this row existed**: she verified, accepted the policy, pressed commit, and had no way to learn whether she was booked | D | unit |
| Entry read failed | the step's own fetch (terms / types / slots / dress) fails rather than returning empty — distinct from every "empty list" row above, which are success responses | D | unit |

**The submit-time `NOT_FOUND` needs a probe, because the server cannot tell you which
thing went.** `POST /storefront/bookings` raises the same `BookingNotFoundError` — and
therefore the same flat `{"code": "NOT_FOUND"}` — for three different causes: the
appointment type is gone, the dress is gone, or the size variant is gone
(`backend/app/booking/service.py`, three sites). The message is the only difference and
this spec forbids reading messages, so the client must ask rather than guess: on a
submit `NOT_FOUND`, re-fetch `/appointment-types` and, if a dress is bound,
`/dresses/{id}`. Type missing ⇒ `booking.typeGoneRepick` and back to the picker. Dress
missing ⇒ drop the binding and continue as a generic appointment. Both still present ⇒
the size variant went; return to the size chips. One row, one deterministic recovery,
no coin flip.

Two behaviours are deliberately *not* states: a **mis-cased or unmatched path** (`/Book`)
silently renders the catalog, because the router has no 404 route and F14 does not add
one — the CTA is the only thing that constructs these paths; and **browser back out of
the first step** leaves the flow to wherever she came from, which is correct and is why
the in-app control is a `<Link>` to a known route.

## Out of scope

The manage/cancel link and every SMS send (F16) · owner-side views of these bookings
(F15) · **taking** a deposit and the payment redirect (E4) — **D3** puts deposit
*disclosure* in scope: `deposit_required` selects the phone-only branch, and
`deposit_amount_agorot`, if shown, must render through the existing price component and
never as a hand-written `₪` (`qa-greps.sh` fails on the glyph) · `brides_only`
enforcement beyond the visual label of **D10** — it needs a client identity (E5) ·
waitlist (E5) · a client dashboard or login (E5) · `.ics` download (E5) · calendar-grid
slot visualisation (E10).

## Testing

**Unit (Vitest + Testing Library, `src/__tests__/`, `TZ=America/New_York` pinned).**
Model on `CatalogPage.test.tsx`: `vi.mock("../api")` spreading `importActual` so
`ApiError`/`errorMessage*` keep real behaviour, render inside the real
`StorefrontLayout`, assert against real Hebrew strings from `i18n`. Cover each step's
validation, every error code's recovery path, the token-expiry path, and the two
mid-flow conflicts (`SLOT_UNAVAILABLE` re-pick, `TERMS_STALE` re-accept).

**Every row of §State matrix marked "unit" gets a test**, and three of them carry an
assertion worth naming because it is easy to write vacuously: a booking-path
`400 VALIDATION_ERROR` must **not** render "השמלה כבר לא זמינה" (i.e. `isNotFound` is
unreachable from this flow); the `notes` and `name` bounds are tested at the boundary —
500 submits and 501 is refused client-side with no request issued, likewise 80 and 81;
and a `deposit_required` type must render the phone-only branch **while a non-deposit
sibling in the same picker stays bookable**, which is the assertion that catches a
branch applied to the whole picker instead of one row.

**Backend (pytest).** The new terms endpoint needs the house treatment: field-allowlist
assertion (`created_by` and `tenant_id` must be absent from the response), the
no-terms state returning `404 NOT_FOUND`, cross-tenant isolation, `no-store`,
cookie-blindness, and its row in `test_storefront_api.py`'s cross-router shadowing
guard. Adding that row is what arms the five derived guard suites — including
`test_the_read_throttle_is_not_inert`, which will fail unless the endpoint actually
spends the per-tenant read budget. `test_frontend_constant_parity.py` gains the two
rows from **D7**.

**E2E (Playwright, `frontend/e2e/storefront.spec.ts`).** Fixture-driven route
interception like the existing specs; add booking fixtures and an axe pass per new
route with `withTags(["wcag2a","wcag2aa"])`. Plus the standing route checks: no
horizontal scroll at 375/768/1440, skip link first Tab stop, reduced-motion honoured.
Two booking-specific pins: `/book/*` renders **no** `BookingCTA` bar at 375 (Risk 6's
`hasBookingBar` default, asserted rather than assumed), and the browser back button
walks the steps in reverse instead of leaving the flow (**D8**).

**Mechanical.** `frontend/scripts/qa-greps.sh` fails on physical-direction classes
(`ml-`, `pl-`, `left-`, `text-left`, …), raw hex colours, `₪`, and `localStorage` —
the booking form must use logical properties throughout, and Latin/numeric runs (phone
numbers, times, the OTP field) need `<bdi dir="ltr">` per the existing bidi precedent.

## Dependencies

F13, F12, F11, F10, F9 — all merged.

**Backend (new dependencies)**: none — the terms endpoint reuses the existing storefront
read router; the backend *work* it carries is §The terms amendment. **Frontend (new
runtime)**: none — D1 adds no router and the
flow adds no form, date-picker or validation library; every gap in §What `packages/ui`
does not have is built in-repo. **Frontend (dev)**: `openapi-typescript` is already a
devDependency but **its adoption is deferred out of this feature** — see §Design.
**Reuses**: `ContactPanel`, `Button`, `BookingCTA`, `Toast`,
`StorefrontLayout`/`useBoutique`,
`matchRoute`/`navigate`/`Link`, `ApiError`/`extractError`/`errorMessage*`, the
`apps/manage/src/validation.ts` pure-function pattern, and the storefront read router's
`_no_store` + `_throttle`. **New env names**: none — the terms endpoint spends the
existing storefront read budget.

**A design gate is required**: no booking screens exist in `.planning/design/screens/`,
and CLAUDE.md makes a design doc non-optional for new frontend screens.
`/spartan:ux prototype` should produce `.planning/design/screens/booking/` before
implementation planning, at 375/768/1440, covering **every row of §State matrix marked
D** — that table exists so this list cannot drift. It also owns the Hebrew: every key in
the §Design inventory is new (~50 of them), and the explanatory sentences for D3, D5 and D4
have no existing component to borrow from (neither `ContactPanel` nor `ContactCard`
carries prose). **That copy is the user's to author, not the builder's, and it gates the
design gate, which gates the plan** — the same lead-time shape the epic already tracks
for SMS sender-ID registration and the Grow account. *Owner: user. Trigger: now.*

## Risks & open items

1. ~~**The dress-carrying URL cannot be a query string.**~~ **Closed by D9**, which
   holds the evidence. *Owner: closed.*
2. **Silence after success.** Until F16, a confirmed booking produces no SMS. The
   ordering is deliberate and recorded in F13's spec, but F14 is where a real customer
   first feels it — which is why D6 makes the confirmation screen carry the whole
   burden. *Owner: F16. Trigger: when F16 ships, revisit the confirmation copy.*
3. **D1 changes shipped, QA'd behaviour, and three test files pin the old one.**
   `AboutPage.test.tsx:277-297` asserts that clicking the CTA reveals a heading named
   `booking.panelTitle`; `CatalogPage.test.tsx:166-185` asserts the CTA disappears when
   the boutique fetch fails ("the CTA would open empty"); `DressPage.test.tsx:250-255`
   asserts it stays enabled on a reserved dress. There is no `BookingCTAButton.test.tsx`
   to point at — a plan that says "extend the existing CTA tests" names a file that does
   not exist. **What they must assert instead, stated so the plan need not guess**:
   `AboutPage` — the CTA navigates to the booking route and opens no dialog; `DressPage`
   — on a reserved dress it stays enabled and navigates carrying the dress id;
   `CatalogPage` — the CTA now renders even when the boutique fetch fails, per **D12**.
   `inline` stays — it is `/about`'s no-fixed-bar requirement. The component docstring is
   amended in the same pass. *Owner: F14 build. Trigger: now.*
4. ~~**Adopting codegen and shipping a flow in one feature.**~~ **Closed by scoping it
   out** (§Design). The `api-client` OWNER note assigns codegen adoption *and* hoisting
   the shared fetch helpers out of two apps to F14; the `generate` script is not even
   turnkey (it needs a running backend with `APP_ENV=dev`). Doing that refactor inside
   the feature that also builds the flow is what would make the estimate meaningless, so
   it is deferred and the OWNER note stays for whoever takes it. *Owner: unassigned —
   the note names no successor, which is the one loose end here.*
5. **Every unmapped booking error code renders the generic apology.** `errorMessageKey`
   covers four codes; the flow introduces **seven** more — `OTP_INVALID`, `OTP_EXPIRED`,
   `PHONE_NOT_VERIFIED`, `SLOT_UNAVAILABLE`, `TERMS_STALE`, `SMS_NOT_CONFIGURED`,
   `SMS_UNAVAILABLE` — seven `switch` cases over six keys (the two `SMS_*` codes share
   one). Missing one is not a crash: it is a bride told "משהו השתבש" when the real answer
   was "the slot was just taken". The §Design i18n inventory is that checklist. *Owner:
   F14 build. Trigger: now — track it as a checklist, not a discovery.*
6. **`hasBookingBar` excludes `/book` by default, silently.** It is a hardcoded
   `catalog || dress` check, so a new route falls through to `false`: no bottom
   reservation, no `A11yMenu` lift, no CTA bar inside the booking flow. That is the
   right outcome — but it is an implicit default nobody chose, and the inverse mistake
   (adding `book` to the list) would put a "book" CTA inside the booking flow. Recorded
   so it stays deliberate. *Owner: F14 build. Trigger: now.*

## Decisions Log

Gate 1, held 2026-07-29 with the user. Seven questions, seven chosen options; **D1–D9**
each name the alternative declined, so a later reader can tell a decision from an
omission. D3 was the user's own call, not a spec recommendation. The six **rev 2**
corrections came from a verification pass over the shipped code afterwards — none
reopens a decision, but two of them change the work a decision implies. That same pass
surfaced two questions D1–D7 had left implicit; they went back to the user and returned
as **D8** and **D9**. **D10–D12 are not gate decisions and record no alternative**: each
one writes down a choice the shipped code had already made or forced, and exists so a
reviewer reads it as deliberate rather than as an oversight.

- **D1 — booking is a route, not a modal.** The option chosen was "Route `/book`: CTA
  navigates to `/book` (optionally `/book?dress=…`); back-button works per step; URL
  recoverable", over a modal behind the shipped CTA. The CTA navigates instead of
  opening the contact panel. Reason: the shared `Modal` is fixed-width with no scroll
  handling and no size variants, and a multi-step form with a slot grid and policy text
  does not fit it; a route also survives an interrupted session. **Two clauses of that
  option met shipped-code constraints, and neither is dropped in silence** — the
  `?dress=` form is impossible (**D9** substitutes a path segment; Risk 1 has the
  evidence), and "back-button works per step" needs each step to own a URL, which is
  **D8**. **rev 2**: the draft justified the route partly by `router.tsx`'s "swap in
  react-router when E3's booking flow needs nested layouts" — that reasoning is void.
  `StorefrontLayout` is mounted *above* the Router app-wide, so these routes nest for
  free; adding `book` is six mechanical edits and **no new dependency**. The competing
  hint — `BookingCTAButton`'s "replaces the panel's contents behind the same button" —
  is overridden here explicitly, not accidentally; Risk 3 is what that costs in shipped
  tests.
- **D2 — Step order is slot → details → terms → OTP, then submit to `confirm`.**
  Declined: the epic brief's OTP-mid-flow order (as that brief read before this gate),
  and terms-first. Reason: the verification token lives 600
  seconds between `/otp/verify` and `POST /bookings`, and a cancellation policy is the
  one screen a bride will actually stop and read. Minting the token last is the only
  ordering where a slow reader is not a failure mode. It puts the policy before the
  identity check, which is unusual and was confirmed deliberately.
- **D3 — Deposit-required appointment types stay visible but are not bookable online.**
  Declined: accepting free bookings for the pilot, and hiding the types until E4. They
  render in the picker with a sentence explaining that booking this service is by phone,
  above a `ContactPanel`. Reason: hiding them makes the boutique's flagship services
  look nonexistent; accepting free bookings silently disables the deposit — the no-show
  defense, and a locked v1 requirement — for exactly the appointments that asked for it.
  E4 replaces the note with the payment redirect and no other part of the flow moves.
  **This was the user's call, not a recommendation the spec could make.**
- **D4 — A size with `quantity = 0` remains selectable, under copy telling her that size
  may need to be ordered in.** Declined: blocking unavailable sizes. Reason: a fitting is
  not a purchase, and F13 deliberately validates only that the variant exists and is
  active. Blocking it in the UI would be a frontend rule stricter than the API that turns
  away a legitimate order-in fitting.
- **D5 — `GET /storefront/terms` returns `404 NOT_FOUND` when a boutique has no terms**,
  and the booking entry point degrades to the contact panel. Declined: `200` with a null
  body. Reason: the house shape for an absent resource, consistent with every sibling.
  **rev 2**: `NOT_FOUND` is the *domain* envelope; an unresolvable Host returns
  `TENANT_NOT_FOUND` from middleware before any handler runs. They are not
  interchangeable, and the client must not treat them as one — nor reuse `isNotFound`,
  which counts `400 VALIDATION_ERROR` as a missing dress. Note the consequence the error
  table now carries: this makes `NOT_FOUND` mean two different things on two different
  calls, so the terms call must branch on its own 404 rather than hand it to the shared
  copy helper.
- **D6 — The confirmation screen makes no promise of an SMS.** Declined: promising the
  text anyway, and gating F14's release on F16. It states the appointment in full and
  tells her to screenshot or save it, since this screen is the only record she gets until
  F16 ships. Reason: F16 has not shipped, so a booking created here sends nothing;
  promising a text that never arrives is precisely the dead end this feature exists to
  remove. One string changes when F16 lands.
- **D7 — `notes` is in the v1 form**, optional, with a 500-character client cap.
  Declined: omitting it for v1. Reason: it is the context a boutique otherwise collects
  by phone ("coming with my mother", accessibility needs), and the backend validation
  already ships. **rev 2 — the draft was wrong twice about how.** Control characters in
  `notes` are **rejected with a 400, never stripped**; nothing in the booking path
  mutates customer text. And the 500-character bound is a *domain* rule
  (`MAX_BOOKING_NOTES_LENGTH` in `backend/app/booking/validation.py`), not a schema one —
  Pydantic's ceiling is `MAX_NOTES_INPUT_LENGTH = 2000`, so a 1,500-character note passes
  the schema and fails the domain check. Both answer the *same* `400 VALIDATION_ERROR`
  envelope, differing only in an English `message` the client never reads, so the client
  is blind to the difference and its cap must mirror 500, not 2000. Note also that
  `notes` deliberately permits tab, LF and CR (it is a paragraph); only `name` carries
  the full C0 ban, because a newline in an SMS-templated value is header-injection
  material. **And the mirror gets a guard**: `test_frontend_constant_parity.py` is a text
  scrape against one hard-coded path and an explicit `MIRRORED_CONSTANTS` tuple. F14 is
  the first feature to mirror a bound into `apps/storefront`, so that test is generalised
  to read both validation files and gains two rows — `MAX_CUSTOMER_NAME_LENGTH` (80) and
  `MAX_BOOKING_NOTES_LENGTH` (500). F10 recorded that it added no rows there; F14 records
  that it adds two, so the silent-drift failure the test exists for cannot open on the
  storefront side.
- **D8 — Every step owns a URL** (`/book/{step}` and `/book/{step}/{dressId}`, with
  `step ∈ {slot, details, terms, verify, confirm}` a closed set and bare `/book`
  rendering the slot step). Declined: a single `/book` route holding the step in
  `useState`, and a two-URL hybrid. Reason: it is the "back-button works per step; URL
  recoverable" clause of the option chosen at D1, and the app never calls
  `history.back()` — the browser's own button does the walking, which `popstate` already
  supports. The cost is honest and accepted: **a later step's URL is *linkable* but not
  *reachable*** — entering `/book/verify` cold, with no picked slot and no live token,
  redirects to `slot`, because the 600-second token lives in memory and cannot survive a
  reload. Those guards are part of the step machine, not an afterthought. `confirm` is
  the one exception and needs stating, because D6 makes it the bride's only record and a
  screenshot round-trip on iOS can reload it: the booking is already written, so
  `confirm` never redirects — with the `201` payload in memory it renders in full, and
  cold it renders a short "your appointment is booked" over `ContactPanel` rather than
  bouncing her to step one. There is no public read-a-booking-by-id endpoint to do
  better, and F14 does not add one. (Step *slugs* are the URL vocabulary; the i18n label
  keys are named after what the step asks for, so the `verify` step's label is
  `booking.stepOtp`. Deliberate, not a typo.)
- **D9 — The dress rides in a path segment, not a query string.** Declined: widening
  `currentPathname()` to `pathname + search`. Reason: the hand-rolled navigation store
  snapshots `window.location.pathname` only, so a query-only change is invisible to
  React and renders as a silent dead link (Risk 1). A path segment matches the shipped
  `/dress/{id}` precedent and touches nothing every other route depends on.
- **D10 — `audience` labels; it does not gate.** A brides-only type renders a badge and
  stays selectable. Reason: this is not a new decision — `GET /storefront/appointment-
  types` discloses `audience` precisely so the UI can label it, and both the schema
  docstring and the service say so outright ("an ANONYMOUS visitor cannot be classified
  as one, so a server-side filter here would be theatre… real enforcement waits for a
  client identity (E5)"). A client-side gate over a field the API ships to everyone would
  be theatre twice over. Recorded because F10 deferred the semantics to F14 and leaving
  it unstated invites a reviewer to read the badge as an oversight.
- **D11 — The appointment type is picked at the top of the `slot` step, not in a step of
  its own.** Reason: `POST /storefront/bookings` requires `appointment_type_id` and no
  earlier version of this spec said where it came from — the verification pass found the
  flow describing a "type picker" in three places while the step list had four steps and
  none of them was it. `GET /storefront/slots` takes no type parameter, so slots are
  type-independent and the choice does not gate the grid; putting *what* above *when* on
  one screen is the smallest shape that closes the hole, keeps D2's ordering exactly as
  the user chose it, and gives D3's deposit branch and D10's badge the screen they
  already assumed. If a type is archived between that screen and submit, `NOT_FOUND` on
  the booking call re-fetches the list and returns her to the picker.
- **D12 — The CTA renders even when the boutique fetch fails, and loses its `boutique`
  prop.** F10 hid the CTA on `/catalog` for a stated reason: the button opened a
  `ContactPanel` built from boutique data, so it "would open empty". D1 removes that
  failure mode — a button that navigates needs no boutique data — which makes the
  guard obsolete and the prop dead. Reason it is recorded rather than left in the risk
  register: it *inverts a shipped, reasoned F10 behaviour* and it changes a shared
  component's interface across three call sites, and a reviewer meeting either as a
  silent diff would be right to stop. (Removing the guard is a one-site edit on
  `/catalog`; removing the prop touches all three call sites.) Note the honest
  consequence: `/book` for a tenant whose boutique fetch failed renders the flow with no
  contact fallback available, so **all three** `ContactPanel` branches — D3's deposit
  note, D5's no-terms entry and the cold-`confirm` screen — must degrade to plain copy
  when `useBoutique()` has nothing.
