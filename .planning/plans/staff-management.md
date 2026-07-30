# Plan: Feature 51 — Staff management section, owner CRUD (Epic SMC, phase SMC-2)

**Status**: Gate 2 self-approved 2026-07-30 under Interview Q1 (F51 is not on Q1's stop-list — F17/F18/F19/F20/F29/F48). The six contradictions below (C1–C6) are amended into the spec as of Task 0; the spec text is the binding statement of each resolution, this file the reasoning.

**Spec**: `.planning/specs/staff-management.md` (Gate 1 self-approved 2026-07-30, D1–D9) · **Design**: `.planning/design/screens/manage-staff/manage-staff.md` + `copy.md` — **do not exist yet; Task 1 authors both** (C5) · **Branch**: `feature/staff-management` · **Created**: 2026-07-30

TDD throughout: in every task below the failing test is written first, then the code that makes it pass. Local gate per task: `make lint` + `make test` for backend tasks, `pnpm -r lint && pnpm -r typecheck && pnpm -r test` for frontend ones. **`db`-marked tests are written here and executed only on CI** — there is no Docker locally. §"What a local run cannot prove" lists what that costs.

F51 ships **no migration** (D1). `test_every_tenant_id_table_has_forced_rls` staying green is the assertion that none snuck in.

---

## Rulings this plan is built on

| Ruling | Effect on the build |
|---|---|
| **SMC epic, locked table** — exactly two owner-only surfaces: the whole staff router and `POST /manage/terms` | The router carries `require_role(StaffRole.OWNER)` at router level; the four `(method, path)` pairs are added to `test_staff_role_gating.OWNER_ONLY`. Nothing else narrows. |
| **SMC ruling 1** (overrides Interview Q11) | Staff sign in with email + password through the unchanged `/manage/auth/login`. No phone OTP, no SMS, no change to `app/auth/router.py`. |
| **Interview Q1** | Gate 2 self-approves. Risks 1, 2 and 9 (out-of-band credential, no reset notification, owner session can reset others' passwords) are **re-nagged in the run report** and are named rows for the F21 audit; they do not stop the build. |
| **Interview Q2 / design gate** | Assembled from shipped `packages/ui` components only — no new component, no promotion. The design gate self-approves, but **designer and `design-critic` must still both accept** (Task 1). |
| **Interview Q3 / pre-decided #47** | `apps/manage/src/i18n/ar.ts` gains F51's keys, values = the approved Hebrew, never `""`. `lng` stays `"he"`, no switcher. |
| **pre-decided #5** | Zero exclamation marks in Hebrew copy — mechanically enforced in `__tests__/i18n.test.ts` (Task 8). |
| **pre-decided #38** | IS 5568 / WCAG 2.0 AA is a **legal** requirement. The a11y items in Tasks 9 and 10 are not optional polish. |
| **LOOP-STATE F51 note** | Deactivation is instantly effective; **do not build a session sweep**. F31's `tests/test_migrations.py` app-role probe is the verified DB seam — cite it, do not re-prove it. **Scope of that ruling, after the 2026-07-30 review:** it is about *deactivation*, where a sweep is provably unnecessary because `resolve_session` re-reads `staff_users`. It says nothing about a *password change*, which gets no such seam for free — `resolve_session` never consults `password_hash`. F51 therefore revokes the target's other sessions on a password write only (spec D4, Risk 9). |

---

## Six contradictions found between the spec and the shipped tree — recorded, resolved, amended in Task 0

The spec is binding and D1–D9 are not re-litigated. These are six places where the document disagrees with the **shipped code**, and a plan cannot proceed without picking one side. Every resolution is the smaller of the two edits and none touches a D-decision's substance.

### C1 — F31 already proved the deactivate half; the spec says F51 "re-proves" it

The spec's Goal says "F31 proved that on real Postgres for the demotion path (`tests/test_staff_role_gating_integration.py`); F51 re-proves it for the deactivate path", and the db test list repeats it. Verified against the file: `test_a_soft_deleted_shift_managers_live_cookie_is_401_not_403` (`tests/test_staff_role_gating_integration.py:262-284`) **already** asserts exactly that on real Postgres, including the docstring "F51's deactivate button rests on this — there is no session sweep." As written, F51's db suite would ship a byte-for-byte duplicate of a shipped test.

**Resolution:** F51's db test asserts the one fact F31's cannot — that the **route's own write** (`DELETE /manage/staff/{staff_id}`, through the service, under the advisory lock, as `boutique_app`) is what kills the session, where F31 used a hand-written `_soft_delete` UPDATE. One test, named `test_deactivating_through_the_route_kills_the_targets_session_on_her_next_request`, whose docstring cites F31's as the seam proof and states what it adds. Amend the spec's Goal and Testing lines to say "through the route" rather than "re-proves".

### C2 — two shipped comments name F51 as the writer that does not exist yet, and one is a live obligation

Verified by `grep -rn "F51" Backend/`:

| Where | Says today | Becomes |
|---|---|---|
| `tests/test_staff_role_gating_integration.py:24-28` (module docstring) | "Nothing in production writes `staff_users.role`: `StaffUsersRepository.insert` does not accept it and the column rides its server_default. `_promote` is therefore a test-only raw UPDATE … **F51 owns the repository writer; when it lands, `_promote` becomes a call to it** rather than a hand-written statement." | The writer landed. `insert` takes `role`; `update` writes it. `_promote` calls the repository. |
| `tests/test_staff_role_gating_integration.py:108-115` (`_promote`) | raw `update(StaffUser).where(...).values(role=role)` | `await StaffUsersRepository().update(session, tenant_id, staff_id, role=role)` |
| `tests/test_provisioning.py:53-57` | "ProvisioningService never writes role — the row rides `staff_users`' server_default … **F51 adds the first writer; until then this is the only thing pinning it.**" | "`StaffUsersRepository.insert` now defaults `role` to OWNER in Python, so provision writes it explicitly and the server_default is belt. The assertion below is still what pins the default owner." |

`_promote` becoming a real call is a *discharged obligation*, not cosmetics: it is the shipped test's own stated plan, and leaving it would mean F31's integration suite exercises a code path production does not have. The `test_provisioning.py` edit is required because the sentence it makes is **false** the moment `insert` gains a Python default (see D-note in Task 4).

### C3 — the i18n selector cannot simply be widened without retiring F15's floor

`Frontend/apps/manage/src/__tests__/i18n.test.ts` builds `HE` from `f15Entries(...)` (keys `nav.bookings` or `booking.*`) and asserts `expect(HE.length).toBeGreaterThan(70)` — "carries the whole copy deck". The spec says "widen the selector … rather than writing a parallel suite". Widening `f15Entries` in place makes that floor **weaker than it looks**: F51's ~40 keys would let F15's 76-row deck shrink by 40 rows and the assertion still pass.

**Resolution (smallest edit that retires nothing):** one generic helper, two constants.

```ts
function entries(bundle: object, match: (key: string) => boolean): [string, string][]
const HE_F15 = entries(he.translation, (k) => k === "nav.bookings" || k.startsWith("booking."));
const HE_F51 = entries(he.translation, (k) => k === "nav.staff" || k.startsWith("staff."));
const HE = [...HE_F15, ...HE_F51];
```

The `> 70` floor keeps reading `HE_F15`; the key-resolution, exclamation-mark, no-`ar`-empty and (new) F51 floor checks read `HE` / `HE_F51`. Declined: widening in place (retires a guard silently) and a second test module (two files to say one thing).

### C4 — hiding the terms publish form leaves the setup blocker pointing at a form that is not there

D9 requires `TermsSection` to hide its publish form for a non-owner. Verified against `components/TermsSection.tsx:80-89`: when no policy exists the section also renders `data-testid="terms-setup-blocker"`, whose last sentence is «יש ליצור גרסה ראשונה **למטה** כדי להשלים את הקמת הבוטיק». Hide the form and that sentence points at nothing — for the exact persona (a shift manager on a boutique with no policy) the blocker exists to serve.

**Resolution:** the blocker stays visible for both roles (a shift manager must know bookings cannot be accepted); its **action sentence** swaps on `role`. Owner: unchanged. Non-owner: «יש לפנות לבעלת הבוטיק כדי להגדיר מדיניות ביטולים.» One ternary, one hardcoded Hebrew string, in the file's existing hardcoded-Hebrew style — F15's D16 rule that F51 does not retrofit these four sections to i18n stands, so this string is **not** an i18n key. Also amend D9 to name it.

### C5 — the design deck the spec's frontend section consumes does not exist

The spec's Copy section says the deck is "Drafted by the designer into `.planning/design/screens/manage-staff/copy.md`". Verified: `.planning/design/screens/` holds `booking`, `design-system`, `manage-booking`, `manage-catalog`, `owner-bookings`, `shift-board` — **no `manage-staff`**. F15's plan could cite an already-accepted deck; this one cannot.

**Resolution:** **Task 1** authors both files before any frontend code, in the shipped `owner-bookings/` two-file shape (`manage-staff.md` screen design + `copy.md` three-table deck with an untranslated `ar` column), and runs the designer / `design-critic` pair to acceptance. The design gate still self-approves under Q2 — what Task 1 buys is the artifact Tasks 8–10 transcribe, not a user gate.

### C6 — the error map has no answer for the one 400 the staff forms can actually produce

D7 routes a wrong or missing `current_password` to `VALIDATION_ERROR` 400 with the exception's own **English** message (`app/errors.py`, `main.py:457`), and the spec's `staff.error.*` map covers only the three 409s plus `NOT_AUTHORIZED`. So the single security control F51 adds beyond the epic's two guards fails in English on a Hebrew console — the exact defect D9 spends a paragraph closing for `NOT_AUTHORIZED`.

**Resolution, and it costs no backend code:** on the self password-change form, a 400 renders that form's own Hebrew message («הסיסמה הנוכחית שגויה. יש להזין את הסיסמה הנוכחית כדי לשנות אותה.») in the field's `error` slot, not through the generic code map. That is only honest because **every other 400 that form can produce is caught client-side by a mirrored bound** — `MIN_STAFF_PASSWORD_LENGTH` and `MAX_PASSWORD_LENGTH` on the password field, `MAX_DISPLAY_NAME_LENGTH` on the name field, and a native `<select>` that cannot emit an unknown role. Which is precisely why the spec mirrors all three constants and pins them in `test_frontend_constant_parity.py`. Declined: a fourth error code for one field (a wire code to move one string), and leaving the English through (IS 5568 is statutory here).

---

All six are amended into the spec in **Task 0**, in the same PR — the `booking-comms.md` / F15 Task-0 precedent for a plan-phase spec amendment.

---

## Task 0 — This plan, and the six spec amendments
`.planning/plans/staff-management.md` (this file), `.planning/specs/staff-management.md`

- Amend the Goal and the db-test bullet: F31 already proves the deactivate half; F51 proves it **through the route** (C1).
- Amend the "What already exists" list with the two stale F51 forward references F51 must discharge (C2).
- Amend the Testing section's i18n line with C3's two-constant form.
- Amend D9 with the setup-blocker action sentence (C4).
- Amend the Copy section: the deck does not exist and is authored by this feature's Task 1 (C5).
- Amend D7's table and the Copy section with C6's field-local Hebrew for `VALIDATION_ERROR` on the self password form, and the mirrored-bounds argument that makes it honest.
- **Done when**: all six are in the spec and this file is committed. No code, no tests.
- Commit: `docs(planning): F51 implementation plan — Gate 2 self-approved`.

---

## Task 1 — The screen design and the Hebrew copy deck (C5)
`.planning/design/screens/manage-staff/manage-staff.md` (**new**), `.planning/design/screens/manage-staff/copy.md` (**new**)

Authored by the designer, reviewed by `design-critic` to ACCEPT (revisions in the same task, the `owner-bookings/` precedent). No code.

**`manage-staff.md`** — the screen design in the shipped shape: components used (all from `packages/ui`: `Card`, `Input`, `Select`, `Button`, `Badge`, `Modal`, `Skeleton`, `EmptyState`), the list→inline-edit→confirm-Modal structure taken verbatim from `components/TypesSection.tsx`, every state from the spec's table (loading / load-failure / loaded / editing / row-action failure / create-submitting / deactivate-confirm), the three breakpoints, and the a11y contract: one `h2` under `ConsoleShell`'s `sr-only` `h1`, `h3` on the create form, `<label>` on every control, native `<select>` for role, 44×44 targets, `focusRing`, contrast checked against `.planning/design/system/tokens.md`, `<bdi dir="ltr">` on the email and **bare `<bdi>`** on `display_name`, and the `DressEditor.tsx:130-136` focus-restore effect on the confirm Modal.

**`copy.md`** — the three-table deck with an `ar` column standing in untranslated, under the register the F15 deck's §0 states. Load-bearing rows:

- `nav.staff`, `staff.heading`, the list/empty/loading/failure lines, the role Badge words (`owner` → «בעלת הבוטיק», `shift_manager` → «אחראית משמרת» — the **word** carries the role, never the colour), the «זו את» self marker.
- The one line that states D2 plainly and claims nothing was sent: «הסיסמה אינה נשלחת לאיש. יש למסור אותה לעובדת בעצמך.»
- Plain-fact sentences for the two refusals: `staff.error.LAST_OWNER_REQUIRED`, `staff.error.STAFF_SELF_MANAGE`, plus `staff.error.DUPLICATE_EMAIL` and `staff.error.NOT_AUTHORIZED`.
- C6's field-local `staff.currentPasswordWrong`.
- C4's non-owner blocker sentence is **not** in this deck — it is hardcoded Hebrew inside `TermsSection.tsx`, per F15's D16.
- **Zero exclamation marks**, no string that claims/implies/hedges a send, every value a real string.

- **Done when**: both files exist, `design-critic` returns ACCEPT, and the deck's Hebrew is what Task 8 transcribes verbatim.
- Commit: `docs(design): F51 staff section design and Hebrew copy deck`.

---

# Part I — the backend

## Task 2 — Constants, bounds, schemas, the three error classes and the three handlers
`Backend/app/models/constants.py`, `Backend/app/auth/schemas.py`, `Backend/app/auth/staff.py` (**new**), `Backend/app/main.py`

**`AuditAction` gains five members** (D8 — no migration; `audit_log.action` is plain TEXT with no CHECK, `0003_auth.py:71-79`), carrying the file's house comment in the shape `BOOKING_*` already uses:

`STAFF_CREATED = "staff_created"` · `STAFF_UPDATED = "staff_updated"` · `STAFF_ROLE_CHANGED = "staff_role_changed"` · `STAFF_PASSWORD_RESET = "staff_password_reset"` · `STAFF_DEACTIVATED = "staff_deactivated"`

**`app/auth/schemas.py`** gains the two bounds beside the shipped `MAX_PASSWORD_LENGTH = 4096`, each with the "why this number" comment the file already uses:

| Constant | Value | Comment |
|---|---|---|
| `MIN_STAFF_PASSWORD_LENGTH` | `10` | NIST SP 800-63B's floor is 8 with no composition rules; 10 because this one is chosen by one person and spoken to another. |
| `MAX_DISPLAY_NAME_LENGTH` | `200` | `display_name` is unbounded TEXT with no CHECK; 200 is `app/boutique/validation.py:36`'s `MAX_APPOINTMENT_TYPE_NAME_LENGTH`. |

…and the wire models. Requests subclass `ForbidExtraModel` (`app/schemas.py:13`); the response is a plain `BaseModel` used as a return-type annotation, never `response_model=`:

```python
class StaffMember(BaseModel):          # id, email, display_name, role, created_at
class CreateStaffRequest(ForbidExtraModel):
    email: EmailStr = Field(max_length=320)     # the LoginRequest spelling
    display_name: str = Field(min_length=1, max_length=MAX_DISPLAY_NAME_LENGTH)
    role: StaffRole                              # unknown value -> 422 -> house 400, never reaches the CHECK
    password: str = Field(min_length=MIN_STAFF_PASSWORD_LENGTH, max_length=MAX_PASSWORD_LENGTH)
class UpdateStaffRequest(ForbidExtraModel):      # every field optional
    display_name / role / password / current_password
```

`password_hash` and `deleted_at` are **absent from `StaffMember` by construction** — not filtered, never modelled.

**`app/auth/staff.py`** starts as the module docstring, the lock statement and the error classes only (the service arrives in Task 5):

- `_STAFF_LOCK = text("SELECT pg_advisory_xact_lock(hashtext('staff:' || :tenant_id))")` — the **namespaced** form, `catalog/service.py:85-86`'s precedent, with that file's comment ("the prefix is a SQL literal and the id is bound — never interpolated") plus D3's reason for not reusing the bare `hashtext(:tenant_id)` key the booking claim holds (`booking/service.py:262`, `booking/owner.py:472`), plus `# ponytail: one lock per tenant's staff table; nothing in a boutique needs finer.`
- `class DuplicateEmailError(Exception)` · `class LastOwnerRequiredError(Exception)` · `class StaffSelfManageError(Exception)`
- `class StaffNotFoundError(DomainNotFoundError)` — 404 with **no new handler**, the `CatalogNotFoundError` precedent; its docstring says the miss covers unknown, soft-deleted and other-tenant ids indistinguishably (RLS, by design).

**`main.py` gains three `*_BODY` literals and three handlers** — enumerated, because there is no error registry and an unmapped typed error is a bare 500:

| Exception | Status | Body |
|---|---|---|
| `DuplicateEmailError` | 409 | `DUPLICATE_EMAIL_BODY` — `{"code": "DUPLICATE_EMAIL", "message": "A staff member with this email already exists."}` |
| `LastOwnerRequiredError` | 409 | `LAST_OWNER_REQUIRED_BODY` — `{"code": "LAST_OWNER_REQUIRED", "message": "The boutique must always have at least one owner."}` (no count — D7) |
| `StaffSelfManageError` | 409 | `STAFF_SELF_MANAGE_BODY` — `{"code": "STAFF_SELF_MANAGE", "message": "You cannot change your own role or deactivate your own account."}` |

**Deliberately NOT registered, so a reviewer can check the list is complete rather than short:** `StaffNotFoundError` → subclasses `DomainNotFoundError`, bound to the base at `main.py:463`; the `current_password` failures → `DomainValidationError`, bound at `main.py:457`; `NotAuthorizedError` → F31's app-wide 403 at `main.py:440`; `NotAuthenticatedError` → app-wide 401; CSRF → the middleware, before routing.

- **Done when**: `make lint` clean, `make test` green. The three handlers ship **registered and unexercised** in this task, deliberately — there is no route to raise them from until Task 6, and that task's `SPEC_ERROR_CODES` set-equality is their proof. No test is invented here for a route that does not exist.
- Commit: `feat(auth): staff bounds, audit actions and three error handlers`.

## Task 3 — The repository writers (TDD, `db`-marked) and the two discharged forward references (C2)
`Backend/app/db/repositories/staff_users.py`, `Backend/tests/test_staff_management_db.py` (**new**), `Backend/tests/test_staff_role_gating_integration.py`, `Backend/tests/test_provisioning.py`

**Tests first**, in a `--- repository writers ---` section of the new `db`-marked module (`pytestmark = pytest.mark.db`), using the `test_booking_service.py:51-93` idioms: NullPool engines in `try/finally`, the **`app_role_url`** fixture (never the superuser — `conftest.py:27-30` states why), `tenant_session` for every write, a fresh `uuid4()` tenant per test.

| Method | Signature | Tests written first |
|---|---|---|
| `insert` (**existing**, gains one kwarg) | `..., role: str = StaffRole.OWNER.value` | omitting `role` still writes `'owner'` (the provision call site, unchanged); passing `'shift_manager'` writes it and comes back out of `by_id` |
| `update` | `(session, tenant_id, staff_id, *, display_name=None, role=None, password_hash=None) -> StaffUser \| None` | each field alone writes and returns the row; two together write one UPDATE; **all three `None` raises nothing and writes nothing** (an empty `.values()` is a SQLAlchemy error — the guard returns `by_id` unchanged); an unknown id → `None`; a soft-deleted row → `None`; `updated_at` moves **without being assigned** (the DB trigger owns it — `platform/service.py:161`'s rule) |
| `soft_delete` | `(session, tenant_id, staff_id, *, at: datetime) -> bool` | sets `deleted_at`, returns `True`; a second call returns `False` (the predicate carries `deleted_at IS NULL`); unknown id → `False`. Returns `bool`, not the row: `DELETE` answers `OkResponse` and the service already holds the row from its post-lock read |
| `count_live_owners` | `(session, tenant_id) -> int` | counts only `role='owner' AND deleted_at IS NULL`; a shift manager and a soft-deleted owner are both excluded; another tenant's owners are invisible (RLS) |
| `list_live` | `(session, tenant_id) -> list[StaffUser]` | live rows only, ordered `created_at` ASC so the founding owner is first and the order is deterministic across page loads |

Every predicate keeps `deleted_at IS NULL` and the redundant `tenant_id` — the class docstring's stated defence-in-depth.

**Why `role` gets a Python default rather than becoming required:** a required kwarg means editing `ProvisioningService.provision` (a shipped file on the tenant-creation path) to say what the default already says. The default costs one line in one file. Its one consequence — the INSERT now emits `role='owner'` instead of letting the server_default fill it — is what makes `test_provisioning.py:53-57`'s comment false, so **that comment is corrected in this task** (C2). The assertion under it (`staff.role == StaffRole.OWNER.value`) is untouched and still pins the default.

**`_promote` becomes a repository call** (`test_staff_role_gating_integration.py:108-115`) and the module docstring's "nothing in production writes `staff_users.role`" paragraph is rewritten (C2). The `from sqlalchemy import update` import goes if `_soft_delete` no longer needs it — it does, so it stays.

- **Done when**: `make lint` clean (`ruff` + `mypy app tests`), `make test` green (these are `db`-marked, so locally they are **collected and deselected**), `make test-db` green on CI. F31's four integration tests must be green **unedited except for `_promote`'s body** — that is the neutrality proof for the repository change.
- Commit: `feat(auth): staff_users role/update/soft-delete/count writers`.

## Task 4 — `StaffService`: create, and the email rules (TDD, fast)
`Backend/app/auth/staff.py`, `Backend/tests/test_staff_service.py` (**new, no DB**)

**Tests first**, against a fake repository pair — pure protocol, no Postgres, so this suite runs locally.

`StaffService.__init__(session_factory)` builds its own `StaffUsersRepository()` and `AuditLogRepository()`, the `AuthService.__init__` shape. **No clock injection**: nothing in F51 branches on time and `deleted_at` is only ever compared to NULL. *Skipped; add when a test needs a frozen instant.*

`list_staff(tenant_id) -> list[StaffUser]` — one `tenant_session`, one `list_live`. No lock, no pagination (D6).

`create(tenant_id, *, email, display_name, role, password, staff) -> StaffUser`:

1. **`email.lower()` in the service, before anything else** (D5). `login` lowercases at `auth/router.py:52` and `by_email` matches exactly, so a row written as `Dana@Bella.example` is an account that can never sign in — a silent, total failure with no error anywhere. `provision` already knows this (`platform/service.py:75`).
2. **No lock** — an insert can only raise the owner count, and a raise never invalidates a decision another transaction already made under the lock (D3). Stated in a comment so its absence reads as a ruling.
3. `by_email` pre-check → `DuplicateEmailError`.
4. `hash_password(password)` (`app/auth/passwords.py:14`), `insert(..., role=role.value)`, then `audit.record(action=STAFF_CREATED, actor_id=staff.id, entity=str(created.id), details={"email": ..., "role": ...})` — same transaction.
5. The `IntegrityError` backstop wraps the **whole `async with tenant_session(...)` block**, `platform/service.py:83-89`'s exact shape — a pre-check races and a 500 on a duplicate email is not an acceptable answer. Catching inside the block would try to raise from an aborted transaction.

Tests: the address is lowercased before it reaches the repository; a duplicate live email raises `DuplicateEmailError` from the pre-check **and**, with the pre-check monkeypatched away, from the `IntegrityError` backstop; the returned object carries no plaintext password anywhere; the audit row carries the email and the role and **no password material, plaintext or hashed** (D8); `hash_password` is called exactly once.

- **Done when**: `make lint` + `make test` green, locally and on CI.
- Commit: `feat(auth): StaffService create — lowercased email, duplicate backstop, audit`.

## Task 5 — The lock protocol: patch, deactivate, and the two guards (TDD, fast)
`Backend/app/auth/staff.py`, `Backend/tests/test_staff_service.py`

**Tests first.** The step order **is** the correctness argument — a test that still passes with the steps reordered is not testing this. Both operations run in one `tenant_session` (`db/tenant.py:16-30` — a real committing transaction with transaction-local RLS context).

1. **`await session.execute(_STAFF_LOCK, {"tenant_id": str(tenant_id)})` — before any read.** `str(tenant_id)`, matching all three shipped call sites; the `||` concatenation needs a text-bound parameter. D3's whole argument: a read taken outside the lock is a stale read, and the guard would then be evaluated against a count another transaction has already invalidated. F15's D5 lesson, restated in the comment.
2. Post-lock `by_id` (already filters `deleted_at IS NULL` and carries the redundant `tenant_id`). `None` → `StaffNotFoundError` → 404 — which is also what another tenant's id answers.
3. **Self-guard**, identity-based (`target.id == staff.id`), covering exactly two things: the `role` field on `PATCH`, and `DELETE` → `StaffSelfManageError` (409). Display name and password on her own row stay legal — `provision` seeds every founding owner with `display_name=owner_email` (`platform/service.py:77`), so this section is where she fixes that (D4).
4. **Last-owner guard**: `count_live_owners(session, tenant_id)`, fired only when the target **is currently a live owner** and the operation would stop that being true — `DELETE` always, `PATCH` only when `role` moves away from `owner`. `count <= 1` → `LastOwnerRequiredError` (409).
5. **Self password change requires `current_password`** (D4): when `password` is present and `target.id == staff.id`, `verify_password(current_password, target.password_hash)`; missing or wrong → `DomainValidationError` (400). An owner resetting *someone else's* password sends no `current_password` — she does not know it, and that is the field's whole point.
6. **No-op detection before the write** (D8 / F15's D3 rule): a `PATCH` whose every value equals what is already stored writes nothing, audits nothing, and answers 200 unchanged. `display_name` compares by equality; `role` by equality; `password` is **never** compared (an argon2 verify against the new value to detect "same password" would be a gratuitous verify and would leak nothing useful) — a supplied `password` is always a change.
7. The write (`update` / `soft_delete(at=datetime.now(UTC))`), then **one audit row per thing that actually changed**, then commit. A `PATCH` moving both name and password writes `STAFF_UPDATED` **and** `STAFF_PASSWORD_RESET`. `details` per D8's table; `STAFF_PASSWORD_RESET` carries `{"self": target.id == staff.id}`.

Tests here (fakes, no DB), each named for the failure it catches:

- **the lock statement is issued before `by_id`** — asserted on the fake session's recorded statement order. This is the test that fails if the read moves back above the lock.
- the lock key is the **namespaced** `'staff:' || :tenant_id` form, not the bare booking-claim key (a literal assertion on the compiled statement text).
- `POST` issues **no** lock statement at all.
- self-demote and self-deactivate each raise `StaffSelfManageError` and write **nothing**; a self rename and a self password change with the right `current_password` both succeed.
- a wrong `current_password` raises `DomainValidationError` and the hash is unchanged; a missing one on the self path does the same; the **other**-person path never consults it.
- the last-owner guard fires on `DELETE` of the sole owner and on a `PATCH` demoting her, and **does not** fire when a second live owner exists, when the target is already a shift manager, or when the `PATCH` moves only the display name.
- a refused guard writes **no** audit row (the `audit.record` fake records zero calls) — the guard raises inside the transaction, so the rollback is what makes this true, and asserting it is what catches an audit row written before the guard.
- a no-op `PATCH` writes no audit row and no UPDATE.
- a `PATCH` moving role and password writes exactly two rows, with the right two actions.

- **Done when**: `make lint` + `make test` green. The concurrency behaviour is Task 7's `db` suite — **CI only**.
- Commit: `feat(auth): StaffService — the last-owner lock, the self-guard and the audit rows`.

## Task 6 — `staff_router.py`, `main.py` wiring, the fast API suite and the `OWNER_ONLY` edit (TDD)
`Backend/app/auth/staff_router.py` (**new**), `Backend/app/main.py`, `Backend/tests/test_staff_api.py` (**new**), `Backend/tests/test_staff_role_gating.py`

**Tests first**, on the `test_booking_owner_api.py` / `test_catalog_api.py` template: a duck-typed `FakeStaffService` assigned to **`app.state.staff_service`** (not `app.dependency_overrides` — `get_staff_service(request)` reads `app.state` directly, the way every other booking dependency does), a `FakeAuthService`, a hardcoded `TenantContext` resolver, no database.

**The router** — `app/auth/staff_router.py`, a fifth `/manage` router:

```python
router = APIRouter(
    prefix="/manage",
    dependencies=[Depends(_no_store), Depends(require_role(StaffRole.OWNER))],
)
Staff   = Annotated[StaffContext, Depends(get_current_staff)]
Service = Annotated[StaffService, Depends(get_staff_service)]
```

- **Owner-only at router level, not per route.** The SMC epic's locked table names this whole router as one of exactly two owner-only surfaces; a route added here later cannot forget the gate, and `test_staff_role_gating`'s walker reads `allowed_roles` off it.
- **`_no_store` is a third local three-line copy**, not an import (D6). The alternative is `app.auth` importing from `app.booking`, which points the dependency arrow backwards to save three lines. The module docstring records it as a decision.
- Every handler takes `staff: Staff` — the acting id is needed for the self-guard and for every audit row. The gate above is what refuses; this is not a second guard. FastAPI's per-request dependency cache collapses the two to one `resolve_session` (`test_gate_does_not_resolve_the_session_twice` proves the shape).
- Module docstring carries the **shadowing warning** the other four already carry: five routers now mount `/manage`, and a duplicated `(method, path)` would silently win or lose on include order.

| # | Method | Path | Body | Answers |
|---|---|---|---|---|
| 1 | `GET` | `/manage/staff` | — | `list[StaffMember]` — a **bare array**, the `GET /manage/appointment-types` precedent for a small list (D6) |
| 2 | `POST` | `/manage/staff` | `CreateStaffRequest` | `StaffMember` |
| 3 | `PATCH` | `/manage/staff/{staff_id}` | `UpdateStaffRequest` | `StaffMember` |
| 4 | `DELETE` | `/manage/staff/{staff_id}` | — | `OkResponse` |

Path parameters and real HTTP verbs are the shipped `/manage` convention (`boutique/router.py`, `catalog/router.py`, `booking/owner_router.py`). The `.claude/rules` RPC / `@QueryValue` guidance is Kotlin boilerplate for another codebase; F15's D7 already ruled this and F51 follows it. `PATCH` and `DELETE` are both inside `CsrfOriginMiddleware.MUTATING_METHODS` (`app/csrf.py:15`) — verified, so the console's cross-origin dev proxy is fenced on all three mutations.

**`main.py` wiring** — two lines:
- `app.state.staff_service = StaffService(get_session_factory())`, beside `app.state.auth_service`.
- `app.include_router(staff_router)` **after** `owner_booking_router`, carrying the fifth instance of the shadowing comment `main.py:624-636` already models, pointing at `test_staff_api.py`'s `ROUTES` table.

**`tests/test_staff_role_gating.py` — the required edit.** `OWNER_ONLY` gains four rows, spelled as the **route-table templates** (the walker reads `route.path`, not a concrete URL — a literal `/manage/staff/<uuid>` would never match and `test_route_table_matches_the_permission_matrix` would red-fail with "routes lock shift_manager out but are not in OWNER_ONLY"):

```python
STAFF_LIST   = ("GET", "/manage/staff")
STAFF_CREATE = ("POST", "/manage/staff")
STAFF_PATCH  = ("PATCH", "/manage/staff/{staff_id}")
STAFF_DELETE = ("DELETE", "/manage/staff/{staff_id}")
OWNER_ONLY = {TERMS_PUBLISH, STAFF_LIST, STAFF_CREATE, STAFF_PATCH, STAFF_DELETE}
```

That is the whole edit to that file. `test_every_manage_route_is_role_gated` and `test_route_table_matches_the_permission_matrix` then cover the new router structurally, over the **live** route table, with no new test written. Note what it does **not** buy: `test_shift_manager_is_admitted_everywhere_except_terms_publishing` walks `test_boutique_api.ROUTES` and `test_catalog_api.ROUTES` only, so the HTTP half for the staff routes is `test_staff_api.py`'s job below.

**`tests/test_staff_api.py`:**

- `ROUTES: list[tuple[str, str, dict | None]]` — all four, with bodies that pass schema validation, driving `test_every_route_requires_authentication` (401 `NOT_AUTHENTICATED`, and the fake records **zero** calls), `test_every_route_is_wired_and_reaches_the_service` (2xx + the service was reached — this is what catches a `/manage` shadow) and the `cache-control: no-store` parametrization.
- `SPEC_ERROR_CODES = {"VALIDATION_ERROR", "NOT_FOUND", "DUPLICATE_EMAIL", "LAST_OWNER_REQUIRED", "STAFF_SELF_MANAGE", "NOT_AUTHORIZED", "NOT_AUTHENTICATED", "CSRF_ORIGIN_MISMATCH"}` with `test_every_spec_error_code_is_asserted` doing the set equality. ⚠ The template computes `covered` from the **`ERROR_CASES` rows only** (`test_catalog_api.py:946-952`), not from every assertion in the module — so the six non-unconditional codes each need an `ERROR_CASES` row, `NOT_AUTHORIZED` included, because the role-refusal test below is a separate function and would not feed the set. **This is the proof for Task 2's three handlers.**
- **Every route refuses `shift_manager`** with the exact `NOT_AUTHORIZED_BODY`, and refuses the shared `UNKNOWN_ROLE` sentinel imported from `test_staff_role_gating` (nothing in that module's import graph reaches this one, so the direction is open — the `test_booking_owner_api.py:38-41` precedent — and the sentinel's tripwire rides along). The fake records **zero** calls in both cases: the gate raises during dependency solving.
- **No response body carries `password` or `password_hash`** — a walk over every route's success body, the storefront `FORBIDDEN_KEYS` idiom. Plus `assert "password_hash" not in StaffMember.model_fields`.
- Email is **lowercased before it reaches the service** (asserted on the fake's recorded argument, not on the response).
- `display_name` empty and over-long, password under `MIN_STAFF_PASSWORD_LENGTH` and over `MAX_PASSWORD_LENGTH`, an unknown `role` string, and an unknown body key each → 400 `VALIDATION_ERROR` (`ForbidExtraModel` + the `RequestValidationError` handler; **not** a 422 — `main.py:444` maps it).
- A `PATCH` carrying `password` on the acting staff's own id with no `current_password` → 400.
- `test_no_route_is_registered_twice_across_routers` (`test_storefront_api.py:564-573`) stays green **untouched** — F51 adds no `/storefront` path.

- **Done when**: `make lint` + `make test` green, locally and on CI. **This is the milestone task**: the whole route table, the three handlers and the owner-only gate are exercised end to end with no Postgres.
- Commit: `feat(auth): /manage/staff router, owner-only gate and app wiring`.

## Task 7 — The `db`-marked suite (written here, executed on CI)
`Backend/tests/test_staff_management_db.py`, `Backend/tests/test_staff_role_gating_integration.py`

Extends the module Task 3 created. NullPool engines in `try/finally`, the `app_role_url` fixture, `asyncio.run` for seeding when a `TestClient` is involved (`test_staff_role_gating_integration.py:15-18`'s loop rule).

- **The headline: the last-owner race.** Two live owners; `asyncio.gather` of two concurrent `deactivate` calls, then separately a deactivate raced against a demote. Exactly one succeeds each time, the loser raises `LastOwnerRequiredError`, and `count_live_owners` is **1** afterwards. **This is the test that fails if the lock is dropped or the count read moves above it** — and it is the one that would pass, wrongly, under the `count(*)`-subquery form D3 rejects. The `test_booking_service.py:290-318` gather template.
- **Create → the new staffer signs in immediately** through the real `/manage/auth/login` with the password the owner set, and `GET /manage/auth/me` reports her role. This proves the lowercase + argon2 + `by_email` seam end to end, which is the one thing a unit test cannot. A row created with a **mixed-case** email signs in with the lowercase form — D5's silent-failure guard.
- **Deactivate through the route** kills the target's live session on her very next request (401 `NOT_AUTHENTICATED`, not 403), with nothing swept (C1). Docstring cites F31's `test_a_soft_deleted_shift_managers_live_cookie_is_401_not_403` as the seam proof and states what this one adds: the write came from `DELETE /manage/staff/{staff_id}` under the lock, as `boutique_app`.
- **Demote `owner → shift_manager` through the route** → that account is 403 on `GET /manage/staff` and 200 on `GET /manage/settings` on its next request. The console half of F31's `test_a_demotion_bites_on_the_very_next_request`, now driven by the product rather than by `_promote`.
- A **soft-deleted email can be re-created** (the partial unique index `idx_staff_users_tenant_email_unique … WHERE deleted_at IS NULL`); a duplicate **live** email is `DuplicateEmailError`, never a 500 — asserted on the pre-check path **and**, with the pre-check monkeypatched away, on the `IntegrityError` backstop.
- Self-deactivate and self-demote each raise `StaffSelfManageError` and write nothing; a self rename and a self password change with the right `current_password` both succeed (and she can then log in with the new one); with the wrong one, 400 and the hash is unchanged.
- **Audit**: one row per actual change with `actor_id`, `entity` and `details`; a no-op `PATCH` writes none; every refused guard writes none. Asserted by reading `audit_log` directly under the tenant session.
- **RLS isolation**: tenant B's owner can neither list, patch nor deactivate tenant A's staff row — 404, indistinguishable from missing.
- **Not re-proven here**: that `boutique_app` can write `role` past 0011's CHECK under forced RLS. `test_migrations.py::test_the_app_role_can_promote_to_shift_manager_but_not_to_an_unknown_role` is F31's deliberate pre-flight for exactly this and already covers both halves; a comment says so.

- **Done when**: `make test-db` green **on CI**. Locally these collect and skip; `make lint` (mypy over `tests`) is the only local signal.
- Commit: `test(auth): db-marked last-owner race, credential seam and RLS isolation`.

---

# Part II — the frontend

## Task 8 — i18n, the API client, the bounds mirror and the parity guard
`Frontend/apps/manage/src/i18n/he.ts`, `…/i18n/ar.ts`, `…/api.ts`, `…/validation.ts`, `…/__tests__/api.test.ts`, `…/__tests__/validation.test.ts`, `…/__tests__/i18n.test.ts`, `Backend/tests/test_frontend_constant_parity.py`

**Tests first** in `api.test.ts` (the shipped fetch-mock pattern) and `validation.test.ts`.

- **`he.ts`**: `nav.staff` + the `staff.*` deck — **every row of Task 1's `copy.md`, verbatim**, including the four `staff.error.<CODE>` rows and C6's `staff.currentPasswordWrong`.
- **`ar.ts`**: the same keys, values = the approved Hebrew standing in untranslated, **never `""`** (i18next's `returnEmptyString` default renders `""` rather than falling back). Appended to the existing file, whose header already says later console features append theirs.
- **`i18n.test.ts`**: C3's two-constant refactor, plus a `HE_F51.length` floor matching the deck's row count. The exclamation-mark and no-empty-`ar` checks then cover F51's keys mechanically, which is the whole reason the selector is widened. The «נשלח/תישלח/בדרך» check reads `HE` too — F51's copy states the password is **not** sent, so it must survive that pattern; if a drafted string trips it, the string is wrong, not the test.
- **`validation.ts`**: `MIN_STAFF_PASSWORD_LENGTH = 10`, `MAX_PASSWORD_LENGTH = 4096`, `MAX_DISPLAY_NAME_LENGTH = 200` in the file's `export const NAME = <digits>;` form (the parity scrape's regex requires exactly that shape), plus `validateStaffDraft(draft)` returning a Hebrew string or `null` — the `validateAppointmentType` shape. **No email validator and no password-strength rule**: the server's `EmailStr` is the authority and D6 declines composition rules.
- **`api.ts`**: `StaffMember`, `CreateStaffRequest`, `UpdateStaffRequest` as snake_case wire interfaces mirroring the Python models verbatim, plus four wrappers on the exported `api` object — `listStaff()`, `createStaff(body)`, `updateStaff(id, body)`, `deactivateStaff(id)`. No case conversion; this app speaks the backend's snake_case verbatim. `apiFetch` already accepts any `method`, so **no plumbing change** — `PATCH` and `DELETE` need nothing new.
- **`Backend/tests/test_frontend_constant_parity.py`** gains a third `MIRRORS` param — `(MANAGE_VALIDATION_TS, app.auth.schemas, ("MIN_STAFF_PASSWORD_LENGTH", "MAX_PASSWORD_LENGTH", "MAX_DISPLAY_NAME_LENGTH"))`, id `"manage-staff"` — and a one-line docstring correction: the manage `validation.ts` now mirrors three backend modules, not one. It reads the TS as **text**, so it stays in the fast no-Docker, no-Node suite. This guard is load-bearing for C6: it is what makes "every 400 this form can produce other than `current_password` is caught client-side" a checked claim rather than a hope.
- **No `vite.config.ts` change** — every endpoint is under `/manage`, which the dev proxy already forwards.

- **Done when**: `pnpm -r lint && pnpm -r typecheck && pnpm -r test` green, `pnpm -r build` clean, and `make test` green (the parity test is a backend test).
- Commit: `feat(manage): staff API client, bounds mirror and Hebrew copy`.

## Task 9 — `StaffSection` — list, inline edit, create, deactivate
`Frontend/apps/manage/src/components/StaffSection.tsx` (**new**), `…/__tests__/StaffSection.test.tsx` (**new**)

**Tests first**, the `CatalogSection.test.tsx` pattern: `vi.mock("../api")` with `importActual` for `ApiError` / `errorMessage`, fixture builders, `vi.mocked`. `axe-core` is **already** a devDependency of `apps/manage` (F15's Task 14 added it) — no new dependency.

Structure, `TypesSection.tsx` verbatim in shape: `<h2>` → a `Card` holding a `<ul>` of staff rows with inline edit → a second `Card` holding the create form (`<h3>`) → one confirm `Modal`. Props: `{ staffId: string }` — the acting owner's id, so the row can carry the self marker and the form can require `current_password`; it comes from `App.tsx`'s already-fetched `Staff`, so the section makes no second identity call.

| Screen | State | Treatment |
|---|---|---|
| List | loading | `<Skeleton variant="text" lines={4} />` |
| List | load failure | `<p role="alert" className="text-sm text-ink-muted">` — the **outage** register |
| List | empty | cannot happen (the acting owner is always in it); no `EmptyState` is built for it |
| List | loaded | rows: display name (bare `<bdi>`), `<bdi dir="ltr">` email, role `Badge`, edit + deactivate buttons, and «זו את» on her own row |
| Row | editing | inline `Input` (name) / native `Select` (role) / password `Input`, save + cancel |
| Row | action failure | `<p role="alert" className="text-sm text-danger">` — the **fix-this** register |
| Create | submitting | button disabled via the `TypesSection.tsx:170-180` `creating` flag |
| Deactivate | confirm | the shared `Modal` with the confirm in a caller-supplied `footer` (`Modal.tsx:5-13`), plus the `DressEditor.tsx:130-136` focus-restore effect — the trigger unmounts while the dialog is open, so native `<dialog>` focus-return would land on `<body>`. The jsdom `<dialog>` stub in `src/test/setup.ts` is what makes this testable. |

- Role `Badge`: `owner → success`, `shift_manager → neutral` (`BadgeVariant` verified at `packages/ui/src/components/Badge.tsx:4`). **The Hebrew word inside the badge carries the role; colour never carries it alone** — the test asserts the word, not the class.
- Both password fields are `type="password"` with **`autoComplete="new-password"`**. Without it the owner's browser offers her *her own* console credential for the new staffer's account — a real way to create an account nobody can sign into.
- The create form carries D2's one line: «הסיסמה אינה נשלחת לאיש. יש למסור אותה לעובדת בעצמך.» Nothing anywhere claims, implies or hedges that anything was sent, because nothing is.
- **Error rendering**: a `staff.error.<CODE>` map keyed on `ApiError.code` for `DUPLICATE_EMAIL`, `LAST_OWNER_REQUIRED`, `STAFF_SELF_MANAGE` and `NOT_AUTHORIZED`, with `errorMessage(error)` as the fallback — **except** on the self password-change control, where a 400 renders `staff.currentPasswordWrong` in the field's own `error` slot (C6). The codes are pinned by `SPEC_ERROR_CODES` in Task 6, so the map cannot silently drift.
- Mutations **patch the list row from the mutation response** rather than refetching (`CatalogSection.tsx:78-80`: the two views cannot disagree if they render one object).
- **Content stays inside `ConsoleShell`'s 720px cap**, which is why the list is rows and not a table. The `Card` padding is **not** overridden — `cn()` is a plain join and a consumer `p-0` loses to `Card`'s baked-in `p-6` at equal specificity.

Also tested: 44×44 targets on every control (`py-4` + `text-base`, no `min-h` literal), `<bdi dir="ltr">` on the email and a **bare** `<bdi>` on `display_name` (`dir="ltr"` on a Hebrew name is itself a bidi defect), no `role="tab"` anywhere, heading order `h2 → h3` with none skipped, and an **`axe` pass at zero violations**:

```ts
import { run } from "axe-core";
expect((await run(container)).violations).toEqual([]);
```

- **Done when**: `pnpm -r lint && pnpm -r typecheck && pnpm -r test` green, `pnpm -r build` clean.
- Commit: `feat(manage): owner-only staff section`.

## Task 10 — The role-filtered nav, and the terms publish form (D9, C4)
`Frontend/apps/manage/src/App.tsx`, `…/components/TermsSection.tsx`, `…/__tests__/Nav.test.tsx` (**new**), `…/__tests__/TermsSection.test.tsx`

**Tests first** in `Nav.test.tsx`.

**`App.tsx`** — `nav` (`:51-58`) becomes the console's single permission-to-UI table:

```ts
const ALL = ["owner", "shift_manager"] as const;
const NAV = [
  { key: "profile", labelKey: "nav.profile", roles: ALL },
  … hours, types, terms, catalog, bookings …
  { key: "staff",   labelKey: "nav.staff",   roles: ["owner"] },
] as const;
```

rendered as `NAV.filter((item) => item.roles.includes(staff.role))` and mapped to `ConsoleShell`'s `{key, label}` — **no `ConsoleShell` change**, its `ConsoleNavItem` contract is untouched.

**This is cosmetics.** The control is F31's server-side `RoleGate`; the filter exists so a shift manager is not shown a door that answers 403. Both sentences go in the code comment, because the failure mode of forgetting them is someone later "simplifying" the server gate away.

**The unreachable-section fallback, corrected.** The spec's D9 says "if the **persisted** `section` is not reachable …". Verified: nothing persists it — `section` is `useState<SectionKey>("profile")` (`App.tsx:20`) and `staff` is fetched once at mount, so on any reload both reset. The case is nonetheless **reachable, and it is a boutique case**: `handleLogout` clears `staff` but not `section`, so an owner sitting on «צוות» who logs out and hands the front-desk browser to a shift manager leaves her on a section her role cannot reach. The guard is therefore derived at render, never stored:

```ts
const reachable = NAV.filter((item) => item.roles.includes(staff.role));
const activeKey = reachable.some((item) => item.key === section) ? section : reachable[0].key;
```

Two lines, cannot go stale, and it also covers the mid-session role change F52's poller would introduce (Risk 3). Declined: resetting `section` inside `handleLogout` (one line, but it only covers the logout path and leaves the poller case open). Amend D9's wording in Task 0.

**`TermsSection`** gains a required `role: string` prop:
- the publish form (`Card` + `<form>`, `:104-140`) renders **only** for `owner`;
- the setup blocker (`:80-89`) stays for both roles, with its action sentence swapped for a non-owner (C4) — hardcoded Hebrew, matching the file's existing style, **not** an i18n key (F15's D16);
- `App.tsx` passes `role={staff.role}`;
- the **five** existing `render(<TermsSection />)` call sites in `__tests__/TermsSection.test.tsx` (`:38, :51, :66, :79, :106`) each gain `role="owner"` — no assertion changes, which is the neutrality proof for the prop.

`Nav.test.tsx` asserts: an owner sees seven nav items including «צוות»; a shift manager sees six and no «צוות»; a shift manager left on the staff section after a logout/login lands on the first reachable one instead of a dead panel; `TermsSection`'s publish form is absent for a shift manager and present for an owner, while the blocker is present for both with different action sentences.

- **Done when**: `pnpm -r lint && pnpm -r typecheck && pnpm -r test` green (including the unedited `TermsSection.test.tsx` assertions), `pnpm -r build` clean.
- Commit: `feat(manage): role-filtered console nav and owner-only terms publishing`.

## Task 11 — Gates and the run report
No files.

Run the verification below, report what ran and what passed, and state **explicitly** that the `db`-marked suites execute only on CI. **Re-nag Risks 1, 2 and 9 in the run report** — the out-of-band credential, the un-notified password reset, and an owner session's ability to reset every other staffer's password. Q1 is why they do not stop the build; they are named rows for the F21 audit. Also carry forward: F34 remains parked on the user's prototype review, and F51's merge does not unpark it. No push, no PR — the orchestrator owns review and shipping.

---

## What a local run cannot prove

No Docker locally, so `pytest -m db` collects and skips.

| Task | Proof that is CI-only | What the local run still gives |
|---|---|---|
| **3** (repository writers) | every assertion in the task, plus F31's four integration tests re-run against the new `_promote` | `ruff` + `mypy` over the new signatures and the one edited call site |
| **7** (the whole `db` module) | the last-owner race, the login seam, deactivate-through-the-route, the `IntegrityError` backstop, RLS isolation | `mypy` over `tests` |

Everything in Tasks 2, 4, 5, 6 and 8–10 verifies locally. **Task 6 is the milestone**: the first point at which the full four-route table, the three exception handlers and the owner-only gate are exercised end to end with no Postgres.

---

## Testing plan → spec criteria

| Spec criterion | Where |
|---|---|
| Route table wired, authenticated, `no-store`, no `/manage` shadow | `test_staff_api.py` `ROUTES` (fast) |
| `SPEC_ERROR_CODES` set equality — all eight codes | `test_staff_api.py` (fast) |
| Every route refuses `shift_manager` and `UNKNOWN_ROLE` with the generic 403 | `test_staff_api.py` (fast) + `test_staff_role_gating.py`'s live-route-table walkers via the `OWNER_ONLY` edit |
| The four staff routes are structurally owner-only | `test_route_table_matches_the_permission_matrix` (fast, unedited beyond `OWNER_ONLY`) |
| No response body carries `password` / `password_hash` | `test_staff_api.py` body walk + `StaffMember.model_fields` assert (fast) |
| Email lowercased before the service; mixed-case row can still sign in | `test_staff_api.py` (fast, shape) + `test_staff_management_db.py` (`db`, truth) |
| Bounds: password min/max, display name, unknown role, unknown key | `test_staff_api.py` (fast) + `validation.test.ts` + `test_frontend_constant_parity.py` |
| **The last-owner race** — lock held, count read under it | `test_staff_service.py` statement-order assert (fast) + `test_staff_management_db.py` `asyncio.gather` (`db`) |
| `POST` takes no lock | `test_staff_service.py` (fast) |
| Self-guard: demote + deactivate refused, rename + self password allowed | both suites |
| `current_password` required on the self path, never on the other | `test_staff_service.py` (fast) + `test_staff_api.py` (fast) + `test_staff_management_db.py` (`db`) |
| Duplicate live email 409 on both the pre-check and the `IntegrityError` backstop; a soft-deleted email is reusable | `test_staff_service.py` (fast) + `test_staff_management_db.py` (`db`) |
| Audit: one row per real change, none on a no-op, none on a refusal, no password material | `test_staff_service.py` (fast) + `test_staff_management_db.py` (`db`) |
| Deactivation bites on the next request, no sweep | `test_staff_management_db.py` (`db`) — F31's `test_a_soft_deleted_shift_managers_live_cookie_is_401_not_403` is the cited seam proof |
| `boutique_app` can write `role` past 0011's CHECK under RLS | `test_migrations.py` (`db`, **unedited** — F31's pre-flight) |
| RLS isolation, tenant B → 404 | `test_staff_management_db.py` (`db`) |
| No migration snuck in | `test_every_tenant_id_table_has_forced_rls` (`db`, unchanged) |
| `_promote` is a repository call; F31's suite still green | `test_staff_role_gating_integration.py` (`db`) |
| Section states, badge words, bidi, focus restore, axe | `StaffSection.test.tsx` |
| Nav filtering, unreachable-section fallback, terms form visibility | `Nav.test.tsx` + `TermsSection.test.tsx` (assertions unedited) |
| Zero exclamation marks, no send claim, no empty `ar` value | `i18n.test.ts` (C3's widened selector) |

**No E2E.** The console's entire e2e surface is two login-screen tests, because `vite preview` runs with no backend and nothing can sign in (`e2e/a11y.spec.ts`). A staff e2e would first need `/manage/**` route interception, which no existing spec builds — net-new infrastructure, not a checkbox. Recorded rather than quietly skipped.

---

## Verification

```
make lint      # ruff check . && ruff format --check . && mypy app tests
               #   + pnpm -r lint && pnpm -r typecheck
               #   + bash Frontend/scripts/qa-greps.sh
make test      # pytest -m "not db" -q
make fe-test   # pnpm -r --if-present test
make fe-build  # pnpm -r build
make e2e       # pnpm -r build && playwright install chromium && pnpm e2e
```

**Green looks like:**

- `make lint` — ruff clean, `ruff format --check` clean, **mypy zero errors over `app` and `tests`**, `pnpm -r lint` and `pnpm -r typecheck` clean across all four workspace packages, and `qa-greps.sh` exit 0 printing **none** of F51's files. F51 adds no date formatter, so the date-read block's output is unchanged from F15's merge (`HoursSection.tsx:15`, `TermsSection.tsx:9`, both pre-existing and warning-only).
- `make test` — all fast tests pass; `test_staff_api.py` and `test_staff_service.py` green; `test_staff_role_gating.py` green with only the `OWNER_ONLY` edit; `test_frontend_constant_parity.py` green with its third param; the `db`-marked modules **collected and deselected**, and the summary line says so.
- `make fe-test` — `StaffSection.test.tsx` and `Nav.test.tsx` green including the axe passes at **zero** violations; `TermsSection.test.tsx` green with **no assertion edits**, only the `role="owner"` prop on its five renders; `i18n.test.ts` green with F15's `> 70` floor still reading F15's keys alone.
- `make fe-build` — both apps build; no unused-import or unused-variable TS error.
- `make e2e` — the existing storefront and console specs stay green. **F51 adds no e2e spec**, so an unchanged e2e count is the expected result, not a gap.
- **CI additionally**: `make test-db` green, including the last-owner race under `asyncio.gather`, the login seam, deactivate-through-the-route, the `IntegrityError` backstop, the audit assertions, the RLS isolation case, and F31's four integration tests unchanged apart from `_promote`'s body.

---

## Out of scope (unchanged from the spec)

Any self-service for a shift manager (her own password, her own display name — widening `UNGATED_ALLOWLIST`'s three-entry posture is a deliberate act, not a corner of F51) · a restore endpoint and a deactivated-staff list (D5) · editing a staff member's email (D5) · forced password change on first login, rotation, breach-list checks, MFA (D1, D6) · an invite flow, a mailer, or any in-product credential delivery (D2) · **a session sweep on deactivation** — `resolve_session` re-reads `staff_users` per request and the LOOP-STATE entry says in as many words not to build one · reading the audit rows (D8) · the other three E6 roles (reception, seamstress, sales) · per-staff permissions or a permission-matrix UI · retrofitting the four hardcoded-Hebrew console sections to i18n and any he/ar parity guard (F15's D16) · an owner-count index (D1, Risk 7) · a client-side email or password-strength validator (D6).
