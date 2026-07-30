# Spec: F51 — Staff management section, owner CRUD (SMC-2)

**Created**: 2026-07-30 · **Status**: **Gate 1 self-approved 2026-07-30 under Interview Q1** (standing approval — F51 is not a money or legal surface; Q1's stop-list is F17, F18, F19, F20, F29, F48 and F51 is not on it). **The design gate self-approves too, under Interview Q2**: the Staff screen is a Card + Input + Select + Button + Badge + Modal list built from shipped `packages/ui` components, and Q2 names exactly two novel patterns — F34's shift board and F42's capacity matrix. Designer and `design-critic` must still both accept. · **Epic**: SMC (`.planning/epics/shift-manager-console.md`), phase SMC-2 · **Effort**: **M** (4 endpoints, no migration, one new console section, one new backend module pair, three new test modules — F15's L was 10 endpoints plus two `packages/ui` promotions)
**Depends on**: #31 (`require_role`, the `RoleGate`, `NotAuthorizedError`, the generic 403 body, the default-deny route walker, and 0011's `CHECK (role IN ('owner','shift_manager'))`) · **Feeds**: F52 and F53 (both land console sections beside this one and inherit its nav table), F34 (the shift board is the first surface a `shift_manager` opens, and until F51 ships there is no way to create one outside `psql`)

---

## Problem

F31 shipped the second `StaffRole`, the DB CHECK that pins it, and a default-deny gate on every `/manage` route. **Nothing can create a `shift_manager`.** `StaffUsersRepository` has exactly three methods — `by_email`, `by_id`, `insert` — and `insert` does not take a `role` at all (`db/repositories/staff_users.py:35-53`), so every row it writes takes the `DEFAULT 'owner'` from `0003_auth.py:39`. The only writer of `staff_users.role` anywhere in the product is a test (`tests/test_migrations.py:127-131`).

So the persona the whole SMC epic is built around cannot exist. The gate F31 shipped is, today, a gate on a population of one. The three surfaces queued behind this one (F52's dashboard, F53's CRM, F34's board) are all specified for "both roles" and none of them can be exercised as the non-owner role until an owner can make one.

The second half is credentials. `AuthService.login` resolves `staff_users` by email and verifies an argon2 hash (`auth/service.py:43-85`); a staff row with no usable password is an account that cannot sign in. The two password writers that exist are both operator-side: `ProvisioningService.provision` seeds the first owner at tenant creation (`platform/service.py:69-78`) and `reset_owner_password` resets one — and that second one carries `StaffUser.role == StaffRole.OWNER` in its WHERE clause (`platform/service.py:168`), so **it structurally cannot help a shift manager who forgets her password**. Without F51 there is no path, operator or otherwise, to a working non-owner credential.

## Goal

`apps/manage` gains a seventh section, **visible only to an owner**. She sees the boutique's live staff, adds one with an email, a display name, a role and a password she chooses; renames one; changes one's role; resets one's password; and deactivates one. Deactivation takes effect on the deactivated staffer's **very next request** — no sweep, no waiting — because `resolve_session` re-reads `staff_users` on every request (`auth/service.py:87-95`) and `by_id` filters `deleted_at IS NULL`. **F31 already proved both halves on real Postgres** — the demotion path and the deactivate path (`test_a_soft_deleted_shift_managers_live_cookie_is_401_not_403`, whose docstring names this feature). F51 does not re-prove them; it proves the one fact F31's cannot, that the **route's own write** (`DELETE /manage/staff/{staff_id}`, through the service, under the lock, as `boutique_app`) is what kills the session, where F31 used a hand-written `_soft_delete` UPDATE. (Plan C1.)

Two invariants hold under concurrency, not just under a single request: **an owner may not deactivate or demote herself**, and **a tenant always has at least one live owner**.

The console nav becomes role-filtered, so a shift manager does not see a section every one of whose routes would answer her a 403.

**F51 ships no migration.**

## What already exists to build on (verified against code)

- **The table is complete.** `staff_users` carries `id`, `tenant_id`, `created_at`, `updated_at`, `deleted_at`, `email`, `password_hash`, `display_name`, `role` (`0003_auth.py:34-41`), with `idx_staff_users_tenant_email_unique ON staff_users(tenant_id, email) WHERE deleted_at IS NULL` (`0003_auth.py:44-46`), an `updated_at` trigger, `GRANT SELECT, INSERT, UPDATE, DELETE ... TO app_user` and forced tenant RLS (`0003_auth.py:83-86`). `0011_staff_roles.py:22-25` pins the role set.
- **The DB seam is already proven for the app principal.** `tests/test_migrations.py::test_the_app_role_can_promote_to_shift_manager_but_not_to_an_unknown_role` is F31's deliberate pre-flight for this feature and says so in its own docstring: `boutique_app`, under forced RLS with only its GRANTs, really can `UPDATE staff_users SET role = 'shift_manager'` past 0011's CHECK, and really cannot write an unknown role. F51 cites it and does not re-prove it.
- **The gate is shipped and introspectable.** `require_role(*allowed) -> RoleGate` with an `allowed_roles: frozenset[str]`, raising `NotAuthorizedError` → a generic 403 `NOT_AUTHORIZED` body (`auth/dependencies.py:40-66`, `main.py:105-108, 440-442`). The per-route tightening pattern is `@router.post("/terms", dependencies=[Depends(require_role(StaffRole.OWNER))])` (`boutique/router.py:215`); the router-level default posture is `APIRouter(prefix="/manage", dependencies=[Depends(require_role(...))])` (`boutique/router.py:31-34`, `catalog/router.py:56-61`, `booking/owner_router.py`).
- **F31's tests already own the policy, and F51 must extend one constant.** `tests/test_staff_role_gating.py:46-50` declares `OWNER_ONLY = {TERMS_PUBLISH}` with the comment "F51's staff router adds its rows here". `test_route_table_matches_the_permission_matrix` walks the **live** route table and fails with "routes lock shift_manager out but are not in OWNER_ONLY" the moment an owner-only gate appears that the set does not name. That is a required edit, not an optional one.
- **The `/manage` posture.** Four routers mount `prefix="/manage"` today and are included in a fixed order with an explicit shadowing warning (`main.py:624-636`); `CsrfOriginMiddleware` fences mutating methods under `/manage` and nowhere else. `_no_store` is a router-level dependency in both `catalog/router.py:42-60` and `booking/owner_router.py`. Paginated lists answer `{items, total, offset, limit}`; small lists answer a bare array (`GET /manage/appointment-types` → `AppointmentType[]`).
- **The house error plumbing.** `DomainNotFoundError` / `DomainValidationError` (`app/errors.py`) give a new module the 404 and 400 with no `main.py` change. A concrete new error needs a body constant plus one `@app.exception_handler` (`main.py:109-175, 467-478`). Request models subclass `ForbidExtraModel` (`app/schemas.py:12-16`); `OkResponse` is the shared `{"ok": true}`.
- **`audit_log` is writable, per-tenant and unconstrained on `action`.** `AuditLogRepository.record(session, *, tenant_id, action, actor_id, entity, details)` joins the caller's transaction (F15's D2, verified again at `0003_auth.py:71-79`). `AuditAction` is a `StrEnum` and needs no migration.
- **The advisory-lock idiom, three shipped copies.** `SELECT pg_advisory_xact_lock(hashtext(:tenant_id))` in `booking/service.py:262`, `booking/owner.py:472` and `boutique/service.py:241`; and the **namespaced** form `hashtext('dress-media:' || :dress_id)` in `catalog/service.py:85-86`. The namespacing detail is load-bearing for D3.
- **The console frontend.** `apps/manage` has no router — sections are a `useState<SectionKey>` plus a flat `nav` array of `{key, label}` handed to `ConsoleShell` (`App.tsx:14, 20, 51-58, 68-74`). `ConsoleShell` renders a plain `<nav>` with `aria-current="page"`, never `role="tab"` (`packages/ui/src/components/ConsoleShell.tsx:26-31, 55-84`). `api.ts` is a hand-written typed fetch client speaking the backend's snake_case verbatim with `credentials: "include"` and an `ApiError {status, code, message}`. `TypesSection.tsx` is the shipped list→inline-edit→confirm-Modal CRUD template.
- **The i18n posture.** `i18n/index.ts` registers `he` and `ar`, `lng: "he"`, `fallbackLng: "he"`, no switcher. `i18n/ar.ts` carries F15's keys with the Hebrew standing in as placeholder values, and its header states the rule: a placeholder must never be `""`, because i18next's `returnEmptyString` default renders `""` rather than falling back. `__tests__/i18n.test.ts` mechanically enforces zero exclamation marks over the keys it selects.
- **Two shipped comments name F51 as the writer that does not exist yet, and F51 must discharge both (plan C2).** `tests/test_staff_role_gating_integration.py:24-28` says "F51 owns the repository writer; when it lands, `_promote` becomes a call to it" — so `_promote` (`:108-115`) becomes `StaffUsersRepository().update(...)` and that paragraph is rewritten. `tests/test_provisioning.py:53-57` says "ProvisioningService never writes role — the row rides the server_default … F51 adds the first writer" — that sentence becomes **false** the moment `insert` gains a Python `role` default, so the comment is corrected in the same task. Its assertion is untouched.
- **The client/server drift guard.** `tests/test_frontend_constant_parity.py` reads `frontend/apps/manage/src/validation.ts` as **text** (so it runs in the fast, no-Docker, no-Node suite) and asserts named constants match a backend module. Its `MIRRORS` tuple takes `(ts_path, python_module, names)`, so a second backend module against the same TS file is one new `pytest.param`.

---

## Design

### No migration (D1)

Every column F51 needs exists, the role set it writes is already CHECK-pinned, the email uniqueness it relies on is already a partial unique index, and `audit_log.action` is plain TEXT with no CHECK. The new `AuditAction` members are `StrEnum` additions only — the same fact `AuditAction.BOOKING_*` already leans on (`constants.py:83-86`).

`test_every_tenant_id_table_has_forced_rls` staying green is the assertion that F51 did not sneak a table in.

Declined, each considered:
- **`must_change_password BOOLEAN`** — see D2. It needs a column, a login-flow branch, a change-password endpoint and a new any-authenticated gating posture; F51 would be building a password lifecycle nobody asked for.
- **A `staff_invitations` table** — there is no channel to deliver an invitation on (D2).
- **`last_login_at`** — nothing renders it and nothing decides on it. Speculative.
- **An index for the owner count** (`(tenant_id) WHERE role = 'owner' AND deleted_at IS NULL`) — a boutique has single-digit staff rows and RLS already narrows the scan to one tenant. Risk 7 names the threshold.

### The initial credential is owner-set and delivered out of band (D2)

Verified before designing, not assumed. There is **no email sender in this repo** — `grep -rn "reset|forgot|invite" Backend/app` returns the operator CLI, a rate-limiter method and two unrelated comments; `app/notifications/` is SMS only. SMC ruling 1 removed SMS from the staff auth path entirely (email + password through the unchanged `/manage/auth/login`), and no sender ID is registered in any case. The two password writers that exist are both operator-side and one of them (`reset_owner_password`) has `role == 'owner'` in its WHERE clause, so it cannot serve this persona at all.

So the honest answer, stated plainly rather than dressed as a flow: **the owner types the new staffer's password into the create form and tells her what it is — by voice, in person, or over whatever channel the boutique already uses.** The API never returns it, never logs it, never echoes it in an audit row. The console says this out loud in one line of Hebrew, and — per the F15 register rule — never claims, implies or hedges that anything was sent, because nothing is.

The same argument makes **password reset a field on `PATCH`**, not an omission: without it, a shift manager who forgets her password has no remedy anywhere in the product, since the operator CLI refuses her by role.

Declined: an invite-token flow (a token needs a channel), a mailer (a new external dependency, a new secret, a new deliverability surface, for one string), server-generated passwords shown once (the owner still has to read it aloud, and a value shown once in a console she may navigate away from is worse than one she chose), and forced-change-on-first-login (D1). **Interview Q10's "invite codes only" is about boutique signup, not staff accounts** — noted so a reader does not mistake it for a ruling on this surface.

### The last-owner guard is an advisory lock, and no index can do this job (D3)

The repo's discipline for a concurrent-correctness invariant is "partial unique index, or advisory lock" (`booking-core.md:66, 81-86`). **Only one of the two applies here, and saying why is the point:** a unique index expresses *at most one* of something. The last-owner invariant is *at least one*. No index, partial or otherwise, can express a minimum.

**A single guarded statement does not work either**, and this is the trap worth writing down:

```sql
UPDATE staff_users SET role = 'shift_manager' WHERE id = :id
  AND (SELECT count(*) FROM staff_users
       WHERE tenant_id = :t AND role = 'owner' AND deleted_at IS NULL) > 1
```

Under READ COMMITTED — Postgres's default and this repo's — two concurrent statements each evaluate that subquery against a snapshot that does not contain the other's uncommitted write. Both see 2, both pass, both commit. The tenant ends with **zero owners** and no error was raised anywhere. The same holds for a deactivate racing a demote.

**The protocol**, in one `tenant_session` (`db/tenant.py` — a real committing transaction with transaction-local RLS context), for `PATCH` when it carries a `role` and for `DELETE`:

1. `SELECT pg_advisory_xact_lock(hashtext('staff:' || :tenant_id))` — **before any read.** Same lesson as F15's D5: a read taken outside the lock is a stale read, and the guard would then be evaluated against a count another transaction has already invalidated.
2. **Namespaced key, deliberately.** The bare `hashtext(tenant_id)` key is the booking-claim lock (`booking/service.py:262`, `booking/owner.py:472`). Reusing it would serialize every staff edit against every public booking create for this tenant — correct but pointlessly wide. `catalog/service.py:85-86` is the in-repo precedent for prefixing the key. In-code: `# ponytail: one lock per tenant's staff table; nothing in a boutique needs finer.`
3. Post-lock read of the target row (`by_id`, which already filters `deleted_at IS NULL` and carries the redundant `tenant_id` predicate). Missing → 404 `DomainNotFoundError`, which is also what another tenant's id answers (RLS makes foreign rows indistinguishable from missing, by design).
4. Self-guard (D4).
5. `count_live_owners(session, tenant_id)` — new repository method, `role = 'owner' AND deleted_at IS NULL`. The guard fires only when the target **is currently a live owner** and the operation would stop that being true: `DELETE` always, `PATCH` only when `role` moves away from `owner`. `count <= 1` → 409 `LAST_OWNER_REQUIRED`.
6. The write, then the audit row(s), then commit.

**`POST` takes no lock.** An insert can only raise the owner count, and a raise never invalidates a decision another transaction already made under the lock. Stated so its absence reads as a ruling.

Declined: `SELECT ... FOR UPDATE` over the owner rows (it locks the rows that exist and cannot prevent a concurrent *insert* from changing the answer — a row-level lock cannot fence a predicate; and every writer of this invariant is already funnelled through one router, which is exactly the condition an advisory lock needs), and `SET TRANSACTION ISOLATION LEVEL SERIALIZABLE` (correct, but it introduces this repo's first serialization-failure retry loop for one guard, and every other concurrency invariant in the product is already an advisory lock).

### An owner may not deactivate or demote herself — and may still rename herself (D4)

The guard is identity-based (`staff.id == target_id`), not count-based, and covers exactly two operations: the `role` field on `PATCH`, and `DELETE`. → 409 `STAFF_SELF_MANAGE`.

Deactivation is instantly effective by construction, so a self-deactivate is a lockout the console cannot undo: there is no restore endpoint (D5), and the operator CLI resets passwords but cannot un-delete a row. Self-demotion is the same lockout one step slower — the staff router is owner-only, so a demoted owner cannot promote herself back.

**Display name and password on her own row stay allowed**, and that matters concretely: `ProvisioningService.provision` seeds the first owner with `display_name=owner_email` (`platform/service.py:77`), so every boutique's founding owner is currently named after her email address and this section is where she fixes it.

**A self password change additionally requires `current_password`.** Four lines, `verify_password` against the row's own hash, 400 on mismatch — and it is the one security control F51 adds beyond the two guards the epic asked for. The reason it is not laziness to skip: a stolen owner session already grants the whole console, but it grants it *for the session's remaining TTL and until a logout*. Letting that same session silently rewrite the owner's password converts a bounded compromise into a permanent takeover whose only remedy is an operator CLI ticket. An owner resetting *someone else's* password sends no `current_password` — she does not know it, and that is the whole point of the field.

Declined: allowing self-demotion when another live owner exists (true that a co-owner could re-promote her, but the guard would then depend on state she cannot see at tap time and the recovery path becomes a phone call), and any self-service password change for a shift manager (see Out of scope — it needs a fifth gating posture, not a corner of F51).

### Email is lowercased on write, and is not editable (D5)

`login` lowercases before lookup (`auth/router.py:52`) and `by_email` matches exactly (`staff_users.py:15-23`). **A staff row created as `Dana@Bella.example` can therefore never sign in** — a silent, total failure with no error anywhere. `provision` already knows this and lowercases (`platform/service.py:75`). F51 lowercases in the service, and pins it with a test.

Uniqueness is the partial index. F51 pre-checks with `by_email` for a clean 409 `DUPLICATE_EMAIL` and maps the flush's `IntegrityError` to the same error as the backstop — the `create_booking` pattern (`booking/service.py:342-345`), because the pre-check races and a 500 on a duplicate email is not an acceptable answer.

**Email is not editable and there is no restore route.** Both fall out of one property: the unique index is partial on `deleted_at IS NULL`, so the moment a row is soft-deleted its address is free again. A typo'd email, a staffer who changes address, and a mis-tapped deactivate all have the same two-tap remedy — deactivate, re-create. Declined: an `email` field on `PATCH` (a login identity moving under a live session, for a need the recreate path already serves) and a `POST /manage/staff/{id}/restore` on the `catalog/router.py:212` dress precedent (a dress carries media, variants and sort order worth preserving; a staff row carries a password hash the owner would have to reset anyway, so restore saves exactly one form field). The list is live-only for the same reason — the archived row has nothing left to offer. Consequence recorded as Risk 5.

### The API (D6)

New module pair: `Backend/app/auth/staff.py` (`StaffService`) and `Backend/app/auth/staff_router.py`. Two files in an existing package, not a new `app/staff/` package for one router — and **not methods on `AuthService`**, which verifies credentials and issues sessions; folding administration into it would put the login path's fake in every CRUD test.

Router: `APIRouter(prefix="/manage", dependencies=[Depends(require_role(StaffRole.OWNER)), Depends(_no_store)])`, included in `create_app()` **after** `owner_booking_router`, carrying the shadowing comment the other four already carry — five routers now mount `/manage` and a duplicated `(method, path)` would silently win or lose on include order.

`_no_store` is a **third local three-line copy**, not an import. The alternative is `app.auth` importing from `app.booking`, which points the dependency arrow backwards to save three lines; hoisting it to a new shared module touches two shipped files for cosmetics. Recorded so the duplication reads as a decision.

The service is constructed once onto `app.state.staff_service` and reached via `get_staff_service(request)` behind a `Service = Annotated[...]` alias — the `booking/owner_router.py` pattern, which is what lets the fast API test swap in a duck-typed `FakeStaffService`.

Every handler takes `staff: Annotated[StaffContext, Depends(get_current_staff)]`: the acting id is needed for the self-guard and for every audit row.

| Method | Path | Body | Answers |
|---|---|---|---|
| `GET` | `/manage/staff` | — | `list[StaffMember]` |
| `POST` | `/manage/staff` | `{"email", "display_name", "role", "password"}` | `StaffMember` |
| `PATCH` | `/manage/staff/{staff_id}` | `{"display_name"?, "role"?, "password"?, "current_password"?}` | `StaffMember` |
| `DELETE` | `/manage/staff/{staff_id}` | — | `OkResponse` |

Path parameters and real HTTP verbs are the shipped `/manage` convention (`boutique/router.py:92, 114, 171`; `catalog/router.py:181, 203, 212`). The `.claude/rules` RPC / `@QueryValue` guidance is Kotlin boilerplate for another codebase and does not apply here — F15's D7 already ruled this and F51 follows it.

**A bare array, no envelope and no pagination.** `GET /manage/appointment-types` is the in-repo precedent for a small list; a boutique's staff table is single-digit. Declined: `{items, total, offset, limit}` — paging controls nobody can reach are the un-lazy thing.

**`StaffMember`** = `{id, email, display_name, role, created_at}`. `password_hash` never reaches the wire, and neither does `deleted_at` (every row in the list is live by construction). Request models subclass `ForbidExtraModel`; responses are plain `BaseModel` return-type annotations, never `response_model=`.

**Bounds** (`app/auth/schemas.py`, beside the shipped `MAX_PASSWORD_LENGTH = 4096`):

| Constant | Value | Why |
|---|---|---|
| `MIN_STAFF_PASSWORD_LENGTH` | `10` | NIST SP 800-63B's floor is 8 with no composition rules; 10 because this password is chosen by one person and spoken to another, so length is the only control that survives that trip. |
| `MAX_PASSWORD_LENGTH` | `4096` (existing) | argon2 cost scales with input size. |
| `MAX_DISPLAY_NAME_LENGTH` | `200` | `display_name` is unbounded TEXT with no CHECK; 200 matches `MAX_APPOINTMENT_TYPE_NAME_LENGTH`. |

`email` reuses `EmailStr = Field(max_length=320)` from `LoginRequest`. `role` is typed as `StaffRole`, so an unknown value is a house 422→400 before it can reach the CHECK.

Declined: composition rules (800-63B advises against them and they push an owner toward `Boutique1!`), rotation, and a breach-list check (a network dependency, on the login path, for a five-account tenant).

### Errors (D7)

| Raised | Code | Status | Handler |
|---|---|---|---|
| duplicate live email on create | `DUPLICATE_EMAIL` | 409 | **new** |
| demote/deactivate the last live owner | `LAST_OWNER_REQUIRED` | 409 | **new** |
| acting staff targets her own role or deactivates herself | `STAFF_SELF_MANAGE` | 409 | **new** |
| wrong/missing `current_password` on a self password change | `VALIDATION_ERROR` | 400 | existing (`DomainValidationError`) — its message is English, so the console renders `staff.currentPasswordWrong` in that field's own `error` slot instead (plan C6) |
| unknown, soft-deleted or other-tenant `staff_id` | `NOT_FOUND` | 404 | existing (`DomainNotFoundError`) |
| bad payload, bad role, short password | `VALIDATION_ERROR` | 400 | existing |
| `shift_manager` or an unknown role on any route | `NOT_AUTHORIZED` | 403 | existing (F31) |
| no session | `NOT_AUTHENTICATED` | 401 | existing |

Three new bodies and three new handlers in `main.py`, fixed English strings in the house shape. Declined: a `LAST_OWNER_REQUIRED` message naming how many owners exist (a count is not the owner's problem to solve) and folding both guards into one code (the console shows two different Hebrew sentences, and the two are different mistakes).

### Audit (D8)

New `AuditAction` members, no migration — `STAFF_CREATED`, `STAFF_UPDATED`, `STAFF_ROLE_CHANGED`, `STAFF_PASSWORD_RESET`, `STAFF_DEACTIVATED`. `actor_id = staff.id`, `entity = str(target.id)`, written in the same transaction as the change.

| Action | `details` |
|---|---|
| `STAFF_CREATED` | `{"email": "...", "role": "shift_manager"}` |
| `STAFF_UPDATED` | `{"display_name": {"from": "...", "to": "..."}}` |
| `STAFF_ROLE_CHANGED` | `{"from": "shift_manager", "to": "owner"}` |
| `STAFF_PASSWORD_RESET` | `{"self": false}` |
| `STAFF_DEACTIVATED` | `{"email": "...", "role": "owner"}` |

**One row per thing that actually changed** — a `PATCH` that moves the role and the password writes two rows; a `PATCH` whose values all match what is already stored writes none and answers 200 unchanged (F15's D3 no-op rule). Role change and password reset keep their own action values rather than folding into `STAFF_UPDATED`, because those are the two questions a security audit actually asks of this table ("who was made an owner", "whose password did someone else change") and each stays one `WHERE action = …`.

**No password material, plaintext or hashed, ever enters `details`.** Emails do: `audit_log` is per-tenant under forced RLS and the email is the identity the row is about.

Nothing reads these rows in v1 — the same ruling F15's D2 made, for the same reason (a history list nobody asked for, in front of a 720px content cap).

### The nav is role-filtered, and the filter is not the control (D9)

`App.tsx`'s `nav` array gains a `roles` field and becomes the console's single permission-to-UI table:

```ts
const NAV = [
  { key: "profile",  labelKey: "nav.profile",  roles: ALL },
  … hours, types, terms, catalog, bookings …
  { key: "staff",    labelKey: "nav.staff",    roles: ["owner"] },
] as const;
```

rendered as `NAV.filter((item) => item.roles.includes(staff.role))`. **The unreachable-section fallback is derived at render, never stored** (plan C10 correction): nothing persists `section` — it is `useState<SectionKey>("profile")` and `staff` is fetched once at mount, so a reload resets both. The case is still real and still a boutique case: `handleLogout` clears `staff` but not `section`, so an owner sitting on «צוות» who logs out and hands the front-desk browser to a shift manager would leave her on a section her role cannot reach. Two lines that cannot go stale:

```ts
const reachable = NAV.filter((item) => item.roles.includes(staff.role));
const activeKey = reachable.some((item) => item.key === section) ? section : reachable[0].key;
```

**This is cosmetics.** The control is F31's server-side `RoleGate`; the nav filter exists so a shift manager is not shown a door that answers 403. Both statements go in the code comment, because the failure mode of forgetting them is someone later "simplifying" the server gate away.

**`TermsSection` gains a `role` prop and hides its publish form for a non-owner.** `POST /manage/terms` is the epic's other owner-only surface and `GET /manage/terms` is not, so the nav item stays visible for both roles while the form does not. **The setup blocker stays visible for both roles and swaps its action sentence** (plan C4): `TermsSection.tsx:80-89` tells a boutique with no policy «יש ליצור גרסה ראשונה למטה», which would point at a form that is no longer there — for exactly the persona it exists to serve. A shift manager must still learn bookings cannot be accepted, so the blocker stays and a ternary swaps its last sentence to «יש לפנות לבעלת הבוטיק כדי להגדיר מדיניות ביטולים.» — hardcoded Hebrew in the file's existing style, **not** an i18n key (F15's D16). Without this, a shift manager taps «פרסום» and gets the generic 403 — whose body message is **English** (`main.py:105-108`) and which `errorMessage()` surfaces verbatim into a Hebrew console. F51 also maps `NOT_AUTHORIZED` to Hebrew in its own `staff.error.*` map. The wider leak (five other sections could show that English string on a mid-session demotion) is Risk 4, not F51's diff.

---

## Frontend changes

### Files

| File | Change |
|---|---|
| `Frontend/apps/manage/src/components/StaffSection.tsx` | **new** — the whole section |
| `Frontend/apps/manage/src/App.tsx` | `NAV` table with `roles`, the `staff` section key, the unreachable-section fallback, `role` passed to `TermsSection` |
| `Frontend/apps/manage/src/components/TermsSection.tsx` | `role` prop; publish form hidden for non-owner |
| `Frontend/apps/manage/src/api.ts` | `StaffMember`, `CreateStaffRequest`, `UpdateStaffRequest` + four endpoints |
| `Frontend/apps/manage/src/validation.ts` | `MIN_STAFF_PASSWORD_LENGTH`, `MAX_PASSWORD_LENGTH`, `MAX_DISPLAY_NAME_LENGTH`, `validateStaffDraft` |
| `Frontend/apps/manage/src/i18n/he.ts` | `nav.staff` + the `staff.*` deck |
| `Frontend/apps/manage/src/i18n/ar.ts` | the same keys, Hebrew standing in, untranslated (Interview Q3 / pre-decided #47) |

**No new `packages/ui` component and no promotion.** The section is `Card`, `Input`, `Select`, `Button`, `Badge`, `Modal`, `Skeleton`, `EmptyState` — all shipped and all exported from `packages/ui/src/index.ts`. That is also the Q2 self-approval argument.

### Layout and states

`TypesSection.tsx` is the template, verbatim in shape: a `Card` holding a `<ul>` of staff rows with inline edit, a second `Card` holding the create form, and one confirm `Modal`.

| Screen | State | Treatment |
|---|---|---|
| List | loading | `<Skeleton variant="text" lines={4} />` |
| List | load failure | `<p role="alert" className="text-sm text-ink-muted">` — the **outage** register |
| List | empty | cannot happen (the acting owner is always in it) — the row for herself carries a muted «זו את» marker instead |
| List | loaded | rows: display name, `<bdi dir="ltr">` email, role `Badge`, edit + deactivate buttons |
| Row | editing | inline `Input` / `Select` / password `Input`, save + cancel |
| Row | action failure | `<p role="alert" className="text-sm text-danger">` — the **fix-this** register |
| Create | submitting | button disabled, the `TypesSection.tsx:170-180` `creating` flag |
| Deactivate | confirm | shared `Modal` with the confirm in a caller-supplied `footer`, plus the focus-restore effect at `DressEditor.tsx:130-136` |

Role `Badge`: `owner → success`, `shift_manager → neutral`. **The Hebrew word inside the badge carries the role; colour never carries it alone.**

The create form's password field is `type="password"` with `autoComplete="new-password"` — without it the owner's own browser offers her *her* console credential for the new staffer's account, which is a real way to create an account nobody can sign into.

### Copy (Hebrew-first, `staff.*`)

The deck **does not exist yet** — `.planning/design/screens/` holds `booking`, `design-system`, `manage-booking`, `manage-catalog`, `owner-bookings` and `shift-board`, and no `manage-staff` (plan C5). This feature's **Task 1** authors both `.planning/design/screens/manage-staff/manage-staff.md` and `copy.md` before any frontend code, in the shipped `owner-bookings/` two-file shape with an untranslated `ar` column, under the approved register:

- **Zero exclamation marks** (pre-decided #5) — mechanically enforced, see Testing.
- **No string claims, promises or hedges that anything was sent** (F15's register rule) — and here it is literally true: the password is delivered by the owner, so one line says so plainly. Draft: «הסיסמה אינה נשלחת לאיש. יש למסור אותה לעובדת בעצמך.»
- Plain-fact wording for the two refusals: the last-owner guard and the self-guard each get one sentence that states the rule, not the error.
- `staff.error.*` maps `DUPLICATE_EMAIL`, `LAST_OWNER_REQUIRED`, `STAFF_SELF_MANAGE` and `NOT_AUTHORIZED` to Hebrew; everything else falls through to `errorMessage(error)`.
- **`staff.currentPasswordWrong` — the one 400 these forms can actually produce (plan C6).** D7 routes a wrong or missing `current_password` to `VALIDATION_ERROR` 400 carrying the exception's own **English** message, so the single security control F51 adds beyond the epic's two guards would fail in English on a Hebrew console — the exact defect D9 spends a paragraph closing for `NOT_AUTHORIZED`. On the self password-change control a 400 therefore renders «הסיסמה הנוכחית שגויה. יש להזין את הסיסמה הנוכחית כדי לשנות אותה.» in the field's own `error` slot rather than through the code map. That is honest only because **every other 400 that form can produce is caught client-side by a mirrored bound** — `MIN_STAFF_PASSWORD_LENGTH` / `MAX_PASSWORD_LENGTH` on the password field, `MAX_DISPLAY_NAME_LENGTH` on the name field, and a native `<select>` that cannot emit an unknown role — which is precisely why all three constants are mirrored and pinned in `test_frontend_constant_parity.py`. Declined: a fourth wire code to move one string. It costs no backend change.

### Accessibility — IS 5568 / WCAG 2.0 AA is a legal requirement (pre-decided #38)

- The nav item is `ConsoleShell`'s plain `<nav>` button with `aria-current="page"` and `aria-controls="console-main"`. **No `role="tab"`.**
- One `h1` (the shell's, `sr-only`); the section heading is `h2`, the create-form heading `h3`. No skipped levels.
- Every `Input` and `Select` carries a real `<label>`; the role select is a native `<select>`.
- 44×44 minimum touch targets; visible focus ring on every control (`focusRing` from `packages/ui`); contrast checked against `.planning/design/system/tokens.md`, not eyeballed.
- Content capped at 720px, which is why the list is rows and not a table.
- **Bidi**: `<bdi dir="ltr">` around the email (Latin inside RTL). Bare `<bdi>` around `display_name` — `dir="ltr"` on a Hebrew name is itself a bidi defect (`BookPage.tsx:1019-1022`).
- The confirm `Modal` restores focus to its trigger; the trigger unmounts while the dialog is open, so native `<dialog>` focus-return would land on `<body>`.

---

## Testing

Tests marked `db` run **only on CI** — there is no Docker locally, so the whole `test_staff_management_db.py` module below is first exercised on the CI runner. **None of F51's tests are `s3`-marked.**

**Fast suite** (no marker, `Backend/tests/test_staff_api.py`, new) — the `test_catalog_api.py` template with a duck-typed `FakeStaffService` on `app.state.staff_service`, fake auth service, hardcoded tenant resolver, no database:

- The `ROUTES` table driving `test_every_route_requires_authentication`, `test_every_route_is_wired_and_reaches_the_service`, and the `cache-control: no-store` parametrization.
- `SPEC_ERROR_CODES` pinned against D7's table, including the two codes the shipped template adds unconditionally.
- **Every route refuses `shift_manager`** with the exact generic 403 body, and refuses the shared `UNKNOWN_ROLE` sentinel.
- **No response body carries `password` or `password_hash`** — a walk over every route's success body, the storefront `FORBIDDEN_KEYS` idiom.
- Email is lowercased before it reaches the service; `display_name`, password min/max and an unknown `role` string each 400.
- A `PATCH` with a `password` on the acting staff's own id and no `current_password` → 400.

**Extend `Backend/tests/test_staff_role_gating.py`** — `OWNER_ONLY` gains the four staff `(method, path)` pairs. That is the whole edit: `test_every_manage_route_is_role_gated` and `test_route_table_matches_the_permission_matrix` then cover the new router structurally, over the live route table, with no new test written. **A builder who skips this edit gets a red build with a confusing message** ("routes lock shift_manager out but are not in OWNER_ONLY"), which is the point.

**db-marked** (`Backend/tests/test_staff_management_db.py`, new; NullPool engines in `try/finally`, the `app_role_url` fixture never the superuser — the `test_booking_service.py:51-93` idioms):

- **The headline: the last-owner race.** Two live owners; `asyncio.gather` of two concurrent deactivations, then separately a deactivation raced against a demotion. Exactly one succeeds each time, the loser answers 409 `LAST_OWNER_REQUIRED`, and `count_live_owners` is 1 afterwards. **This is the test that fails if the lock is dropped or the count read moves above it.** The `test_booking_service.py:290-318` gather template.
- Create → the new staffer signs in immediately through the real `/manage/auth/login` with the password the owner set. Proves the lowercase + argon2 + `by_email` seam end to end, which is the one thing a unit test cannot.
- Deactivate **through the route** (`DELETE /manage/staff/{staff_id}`, under the lock, as `boutique_app`) → the target's live session is dead on her **very next request** (401), with nothing swept. F31 already proved the seam with a hand-written UPDATE; this proves the product's own write does it (plan C1).
- Demote `owner → shift_manager` → that account is 403 on `GET /manage/staff` and 200 on `GET /manage/settings` on its next request.
- A soft-deleted email can be re-created (the partial unique index); a duplicate **live** email is 409 `DUPLICATE_EMAIL`, never a 500 — asserted on both the pre-check path and, with the pre-check monkeypatched away, on the `IntegrityError` backstop.
- Self-deactivate and self-demote each 409 `STAFF_SELF_MANAGE` and write nothing; a self rename and a self password change with the right `current_password` both succeed; with the wrong one, 400 and the hash is unchanged.
- Audit: one row per actual change with `actor_id`, `entity` and `details`; a no-op `PATCH` writes none; every refused guard writes none.
- RLS isolation: tenant B's owner can neither list, patch nor deactivate tenant A's staff row (404, indistinguishable from missing).
- **Not re-proven here**: that `boutique_app` can write `role` past 0011's CHECK under RLS. `test_migrations.py::test_the_app_role_can_promote_to_shift_manager_but_not_to_an_unknown_role` is F31's pre-flight for exactly this and already covers both halves.

**Frontend (vitest, `apps/manage/src/__tests__/`)** — the `CatalogSection.test.tsx` pattern (`vi.mock("../api")` with `importActual` for `ApiError` / `errorMessage`, fixture builders, `vi.mocked`):

- `StaffSection.test.tsx` — list states, create, inline edit, role change, deactivate + confirm Modal + focus restore (the jsdom `<dialog>` stub in `src/test/setup.ts` is required), the error-code→Hebrew map, the «זו את» self marker, and an axe pass.
- `Nav.test.tsx` — an owner sees seven nav items including Staff; a shift manager sees six and no Staff; a shift manager landed on an unreachable section falls back to the first reachable one; `TermsSection`'s publish form is absent for a shift manager and present for an owner.
- `i18n.test.ts` — **widen the selector, without retiring F15's floor** (plan C3). Widening `f15Entries` in place would make `expect(HE.length).toBeGreaterThan(70)` weaker than it looks: F51's ~40 keys would let F15's deck shrink by 40 rows and still pass. So: one generic `entries(bundle, match)` helper and two constants — `HE_F15` (`nav.bookings` / `booking.*`) keeps the `> 70` floor, `HE_F51` (`nav.staff` / `staff.*`) gets its own floor, and the key-resolution, exclamation-mark and no-empty-`ar` checks read `HE = [...HE_F15, ...HE_F51]`.
- `validation.test.ts` — the password and display-name bounds.

**`tests/test_frontend_constant_parity.py`** gains a third `MIRRORS` param: `(MANAGE_VALIDATION_TS, app.auth.schemas, ("MIN_STAFF_PASSWORD_LENGTH", "MAX_PASSWORD_LENGTH", "MAX_DISPLAY_NAME_LENGTH"))`. It reads the TS as text, so it stays in the fast no-Node suite.

**No E2E.** The console's entire e2e surface is two login-screen tests, because `vite preview` runs with no backend and nothing can sign in (`e2e/a11y.spec.ts:126-140`). A staff e2e would first need `/manage/**` route interception, which no existing spec builds. Recorded rather than quietly skipped.

---

## Out of scope

- **Any self-service for a shift manager** — change her own password, change her own display name. Every one of those needs a route gated "any authenticated staff", and F31's `UNGATED_ALLOWLIST` has exactly three entries with a comment explaining each; widening that posture is a deliberate act, not a corner of F51. She asks the owner.
- **A restore endpoint and a deactivated-staff list** (D5). Deactivate + re-create is the two-tap remedy the partial unique index already gives.
- **Editing a staff member's email** (D5).
- **Forced password change on first login, password rotation, breach-list checks, MFA** (D1, D6).
- **An invite flow, a mailer, or any out-of-product credential delivery** (D2). The owner tells her.
- **A session sweep on deactivation.** `resolve_session` re-reads `staff_users` per request; F31 proved it on real Postgres and the LOOP-STATE entry says in as many words: do not build one.
- **Reading the audit rows** — same ruling as F15's D2. Written, not rendered.
- **The other three E6 roles** (reception, seamstress, sales). 0011's comment names them as the next to join `StaffRole` when E6-proper gives them a first consumer; pre-adding them is the un-lazy thing.
- **Per-staff permissions or a permission matrix UI.** The epic locks two roles and one owner-only surface set.
- **Retrofitting the four hardcoded-Hebrew console sections to i18n, and any he/ar parity guard** — inherited from F15's D16, unchanged.

---

## Risks & open items

1. **The initial password is delivered out of band and the product cannot enforce a change.** The owner chooses it, speaks it, and nothing logs or expires it; a boutique that reuses one password across three staffers is invisible to the platform. Accepted because no delivery channel exists (D2) and inventing one means a mailer. Bounded by the argon2 hash, the per-`(tenant, email)` and per-IP login limiter (`auth/router.py:54-62`), and the audit row on every reset. *Owner: **user** (to overturn, not to authorise). Trigger: the F21 security audit, or the first pilot boutique with more than two staff.*
2. **A staffer whose password the owner resets is not notified.** There is no channel. She discovers it by failing to log in. *Owner: team. Trigger: transactional email arriving, or a registered SMS sender ID.*
3. **The nav is filtered once, at bootstrap.** `api.me()` runs in a single mount effect (`App.tsx:22-28`), so an owner demoted by a co-owner keeps a stale Staff item until she reloads — every call inside it 403s correctly, but the door is still drawn. A poller is not built: F52's dashboard introduces the console's first repeating fetch and is the natural place to refresh `me()`. *Owner: team. Trigger: F52, or a pilot report.*
4. **The generic 403 body is English and `errorMessage()` surfaces the server's text verbatim.** F51 maps `NOT_AUTHORIZED` to Hebrew inside its own section and hides the one owner-only control outside it (the terms publish form), but the other five sections would still render an English sentence in a Hebrew console on a mid-session demotion. Not F51's diff; named so it is not discovered in the pilot. *Owner: team. Trigger: the console-wide error-copy pass, or F52/F53's own error maps.*
5. **A mis-tapped deactivate is recovered by re-creating the account, which mints a new id.** The old row's `actor_id` on every audit row it wrote can no longer be resolved to a name, because `by_id` filters `deleted_at IS NULL`. Costs nothing today — nothing reads audit rows (D8, F15's D2) — but it is a real hole in whatever renders them later. *Owner: team. Trigger: the audit-read follow-up (F15 Risk 7).*
6. **The advisory lock serializes every staff role change and deactivation for a tenant.** Free at any scale a boutique reaches; recorded for symmetry with `booking-core.md` Risk 2, and marked in code with the same upgrade-path comment. *Owner: team. Trigger: none realistically.*
7. **`count_live_owners` is a sequential scan.** No index supports it and F51 adds none (D1); RLS narrows it to one tenant's single-digit rows. *Owner: team. Trigger: any tenant crossing ~1,000 staff rows — which would mean the product is no longer a boutique platform.*
8. **Nothing keeps `apps/manage/src/i18n/ar.ts` in sync with `he.ts`.** Inherited from F15 Risk 5, unchanged: no parity guard exists and F51 does not invent one, because inventing it means owning it for every remaining feature. *Owner: team. Trigger: the feature that makes Arabic selectable.*
9. **A stolen owner session can still reset every *other* staffer's password without knowing it** — `current_password` is required only on the self path (D4), by design, since an owner does not know her staff's passwords. The compromise this leaves is "an attacker with a live owner session can lock out every staffer but the owner", which is strictly smaller than the console access she already has. *Owner: user. Trigger: the F21 security audit.*

---

## Decisions Log

- **D1 — F51 ships no migration, and its five new `AuditAction` values need none.** `staff_users` already carries every column; 0011 already pins the role set; `idx_staff_users_tenant_email_unique` already enforces uniqueness on live rows; `audit_log.action` is plain TEXT with no CHECK. Declined: `must_change_password`, a `staff_invitations` table, `last_login_at`, and an owner-count index (Risk 7 names the threshold).
- **D2 — The initial credential is owner-set and delivered out of band, and password reset is a `PATCH` field.** Verified before designing: no mailer exists anywhere in `Backend/app`, SMC ruling 1 removed SMS from the staff auth path, and `reset_owner_password` carries `role == 'owner'` in its WHERE clause so it structurally cannot serve a shift manager. The console says so in one line and — per the F15 register rule — never claims anything was sent. Declined: an invite-token flow, a mailer, a server-generated password shown once, and forced-change-on-first-login. Interview Q10's "invite codes only" governs boutique signup, not staff accounts.
- **D3 — The last-owner guard is a namespaced per-tenant advisory lock, taken before the read.** No unique index can express *at least one*, and a single guarded `UPDATE` with a `count(*)` subquery is unsafe under READ COMMITTED — two concurrent statements both see 2 and the tenant ends with zero owners, silently. The key is `hashtext('staff:' || tenant_id)`, not the bare `hashtext(tenant_id)` the booking claim uses, so staff edits do not serialize against public booking creates (`catalog/service.py:85-86` is the prefix precedent). `POST` takes no lock — an insert can only raise the count. Declined: `SELECT … FOR UPDATE` (a row lock cannot fence a predicate against a concurrent insert) and SERIALIZABLE isolation (correct, but it introduces this repo's first retry loop for one guard).
- **D4 — The self-guard covers role change and deactivation only; rename and self password change stay legal, and the latter requires `current_password`.** Deactivation is instantly effective, so self-deactivate is a lockout with no in-product remedy; self-demote is the same lockout one step slower, since the router is owner-only. Rename must stay legal because `provision` seeds every founding owner with `display_name = owner_email`. The `current_password` check is four lines and converts a stolen session from a permanent takeover into a bounded one. Declined: allowing self-demotion when a co-owner exists (the guard would depend on state she cannot see, and the recovery path becomes a phone call).
- **D5 — Email is lowercased on write, is not editable, and there is no restore route or deactivated list.** `login` lowercases before lookup and `by_email` matches exactly, so a mixed-case row is an account that can never sign in — a silent total failure. Uniqueness is pre-checked for a clean 409 with the `IntegrityError` as backstop (the `create_booking` pattern). No restore, no email edit and no archived list all fall out of one property: the unique index is partial on `deleted_at IS NULL`, so deactivate + re-create is a two-tap remedy for all three. Declined: a `/restore` route on the dress precedent (a dress carries media and variants worth preserving; a staff row carries a hash that must be reset anyway).
- **D6 — Two new files in `app/auth/`, a fifth `/manage` router, a bare-array list, and a third local `_no_store`.** Not a new `app/staff/` package for one router, and not methods on `AuthService` (which verifies credentials — folding administration in would put the login fake in every CRUD test). `GET /manage/appointment-types` is the precedent for an unpaginated list; a boutique's staff table is single-digit. `_no_store` is copied rather than imported because `app.auth` importing from `app.booking` points the dependency arrow backwards to save three lines. Declined: `{items, total, offset, limit}` and paging controls nobody can reach.
- **D7 — Three new error codes, all 409: `DUPLICATE_EMAIL`, `LAST_OWNER_REQUIRED`, `STAFF_SELF_MANAGE`.** Everything else reuses a shipped handler — `DomainNotFoundError` for an unknown, soft-deleted or foreign `staff_id`, `DomainValidationError` for a bad payload or a wrong `current_password`, and F31's `NOT_AUTHORIZED`. Declined: a message naming how many owners exist, and folding the two guards into one code (two different mistakes, two different Hebrew sentences).
- **D8 — Five `AuditAction` members, one row per thing that actually changed, no password material in `details`.** Role change and password reset keep their own values because those are the two questions a security audit asks of this table, and each stays one `WHERE action = …`. A no-op `PATCH` writes no row and answers 200 unchanged (F15's D3 rule). Emails do enter `details` — `audit_log` is per-tenant under forced RLS and the email is the identity the row is about. Nothing reads these rows in v1 (F15's D2).
- **D9 — The nav becomes a role table in `App.tsx`, and the code says out loud that it is cosmetics.** The control is F31's server-side `RoleGate`; the filter exists so a shift manager is not shown a door that answers 403. An unreachable section falls back to the first reachable one, **derived at render rather than stored** — nothing persists `section`, but `handleLogout` clears `staff` and not `section`, so the shared front-desk browser reaches the case. `TermsSection` additionally hides its publish form for a non-owner, because the alternative is the generic 403's English message rendering into a Hebrew console — and its setup blocker stays visible for both roles with a role-swapped action sentence, so a shift manager on a policy-less boutique is not pointed at a form that is not there (plan C4). The wider version of the English-403 leak is Risk 4 and is not F51's diff.
